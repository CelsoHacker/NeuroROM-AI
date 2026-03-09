# -*- coding: utf-8 -*-
"""
Utilitarios comuns do Runtime QA (deterministico e auditavel).
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


CRC_RE = re.compile(r"([A-Fa-f0-9]{8})")


PLATFORM_ALIASES = {
    "nes": "nes",
    "nintendinho": "nes",
    "famicom": "nes",
    "snes": "snes",
    "super nintendo": "snes",
    "super nintedo": "snes",
    "nintendo 64": "n64",
    "nintedo 64": "n64",
    "n64": "n64",
    "mega": "megadrive",
    "mega drive": "megadrive",
    "genesis": "megadrive",
    "master system": "master_system",
    "sms": "master_system",
    "playstation 1": "ps1",
    "playstation": "ps1",
    "ps1": "ps1",
    "psx": "ps1",
    "gba": "gba",
    "game boy advance": "gba",
    "sega cd": "segacd",
    "mega cd": "segacd",
    "segacd": "segacd",
}


SUPPORTED_PLATFORMS = (
    "nes",
    "snes",
    "n64",
    "megadrive",
    "master_system",
    "ps1",
    "gba",
    "segacd",
)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            if raw.lower().startswith("0x"):
                return int(raw, 16)
            return int(raw)
        except Exception:
            return default
    return default


def normalize_platform_name(value: str) -> str:
    low = str(value or "").strip().lower()
    if not low:
        return "master_system"
    if low in SUPPORTED_PLATFORMS:
        return low
    if low in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[low]
    for k, v in PLATFORM_ALIASES.items():
        if k in low:
            return v
    return low.replace(" ", "_")


def infer_platform_from_path(path_like: str, fallback: str = "master_system") -> str:
    low = str(path_like or "").lower()
    for token, platform in PLATFORM_ALIASES.items():
        if token in low:
            return platform
    return normalize_platform_name(fallback)


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def load_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default or {})
    if isinstance(obj, dict):
        return obj
    return dict(default or {})


def write_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        if isinstance(meta, dict):
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def compute_crc32(path: Path) -> str:
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def infer_crc_from_name(path_like: str) -> Optional[str]:
    m = CRC_RE.search(str(path_like or ""))
    if m:
        return str(m.group(1)).upper()
    return None


def _offset_sort_tuple(row: Dict[str, Any], idx: int) -> Tuple[int, int, int, int]:
    bank = parse_int(row.get("bank"), default=None)
    page = parse_int(row.get("page"), default=None)
    seq = parse_int(row.get("seq"), default=None)
    off = parse_int(
        row.get("rom_offset", row.get("offset", row.get("origin_offset"))),
        default=None,
    )
    if off is None:
        off = 1 << 30
    return (
        bank if bank is not None else (1 << 20),
        page if page is not None else (1 << 20),
        seq if seq is not None else off,
        idx,
    )


def load_pure_text(pure_jsonl: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    meta: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for idx, obj in enumerate(iter_jsonl(pure_jsonl)):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        row = dict(obj)
        row["_idx"] = idx
        rows.append(row)
    rows.sort(key=lambda r: _offset_sort_tuple(r, int(r.get("_idx", 0))))
    return meta, rows


def extract_seed_items(
    rows: List[Dict[str, Any]],
    limit: int = 256,
    only_safe: bool = True,
) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []
    for row in rows:
        if only_safe and not bool(row.get("reinsertion_safe", False)):
            continue
        off = parse_int(
            row.get("rom_offset", row.get("offset", row.get("origin_offset"))),
            default=None,
        )
        if off is None or off < 0:
            continue
        max_len = parse_int(row.get("max_len_bytes", row.get("max_len")), default=0) or 0
        if max_len <= 0:
            max_len = max(parse_int(row.get("raw_len"), default=0) or 0, 1)
        seed = {
            "id": parse_int(row.get("id"), default=None),
            "key": str(row.get("key", row.get("id", f"off_{off:X}"))),
            "seq": parse_int(row.get("seq"), default=None),
            "rom_offset": int(off),
            "rom_offset_hex": f"0x{int(off):06X}",
            "max_len_bytes": int(max_len),
            "terminator": parse_int(row.get("terminator"), default=None),
            "raw_len": int(parse_int(row.get("raw_len"), default=max_len) or max_len),
            "raw_bytes_hex": str(row.get("raw_bytes_hex", "") or "").replace(" ", "").upper(),
            "context_tag": str(row.get("context_tag", "") or ""),
            "reinsertion_safe": bool(row.get("reinsertion_safe", False)),
        }
        seeds.append(seed)
        if len(seeds) >= max(1, int(limit)):
            break
    return seeds


def infer_crc_size(meta: Dict[str, Any], pure_jsonl: Path) -> Tuple[str, int]:
    crc = str(meta.get("rom_crc32", "") or "").upper().strip()
    if not crc:
        crc = infer_crc_from_name(pure_jsonl.name) or infer_crc_from_name(str(pure_jsonl.parent)) or "UNKNOWN000"
    size = parse_int(meta.get("rom_size"), default=None)
    if size is None:
        manifest = pure_jsonl.parent.parent / "crc_bootstrap_manifest.json"
        if manifest.exists():
            man = load_json(manifest, {})
            size = parse_int(man.get("rom_size"), default=None)
    if size is None:
        size = 0
    return crc, int(size)


def default_runtime_dir(pure_jsonl: Path, crc32: str, out_base: Optional[Path] = None) -> Path:
    if out_base is not None:
        return Path(out_base).expanduser().resolve() / str(crc32).upper() / "runtime"
    p = pure_jsonl.resolve()
    # Estrutura alvo: .../ROMs/<Console>/<CRC32>/1_extracao/<CRC32>_pure_text.jsonl
    if p.parent.name.lower() == "1_extracao":
        crc_dir = p.parent.parent
        console_dir = crc_dir.parent
        return console_dir / "out" / str(crc32).upper() / "runtime"
    return p.parent / "runtime"


def load_platform_profile(platform: str, profiles_root: Optional[Path] = None) -> Dict[str, Any]:
    plat = normalize_platform_name(platform)
    root = profiles_root or (Path(__file__).resolve().parent / "profiles")
    path = root / f"{plat}.json"
    if not path.exists():
        path = root / "master_system.json"
    profile = load_json(path, {})
    if not profile:
        profile = {"platform": plat, "default_terminators": [0]}
    profile.setdefault("platform", plat)
    profile.setdefault("default_terminators", [0])
    profile.setdefault("autoplay_sequence", [])
    profile.setdefault("pointer_registers", [])
    profile.setdefault("buffer_registers", [])
    return profile


def english_stopword_hit_count(text: str) -> int:
    if not text:
        return 0
    low = f" {text.lower()} "
    words = (
        " the ",
        " you ",
        " your ",
        " this ",
        " there ",
        " then ",
        " that ",
        " with ",
        " from ",
        " attack ",
        " option ",
        " options ",
    )
    return sum(1 for w in words if w in low)


def classify_context(frame: int) -> str:
    if frame < 1800:
        return "intro"
    if frame < 3600:
        return "menu"
    if frame < 9000:
        return "dialog"
    return "gameplay"

