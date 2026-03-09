#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera script Python de AutoProbe para runtime libretro.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .common import (
        default_runtime_dir,
        extract_seed_items,
        infer_platform_from_path,
        infer_crc_size,
        load_platform_profile,
        load_pure_text,
        write_json,
    )
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        default_runtime_dir,
        extract_seed_items,
        infer_platform_from_path,
        infer_crc_size,
        load_platform_profile,
        load_pure_text,
        write_json,
    )


def _render_runner_script(config_path: Path, project_root: Path) -> str:
    cfg = str(config_path).replace("\\", "\\\\")
    root = str(project_root).replace("\\", "\\\\")
    return f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(r"{root}")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.runtime_qa.libretro_runtime_runner import run_probe

result = run_probe(Path(r"{cfg}"))
print(json.dumps(result, ensure_ascii=False, indent=2))
"""


def build_probe_payload(
    pure_jsonl: Path,
    core_path: Path,
    rom_path: Path,
    platform_hint: Optional[str] = None,
    seeds_limit: int = 256,
    max_frames: int = 18000,
    sample_every_frames: int = 6,
    out_base: Optional[Path] = None,
) -> Dict[str, Any]:
    meta, rows = load_pure_text(pure_jsonl)
    platform = platform_hint or infer_platform_from_path(str(pure_jsonl), fallback="master_system")
    profile = load_platform_profile(platform)
    crc, rom_size = infer_crc_size(meta, pure_jsonl)
    seeds = extract_seed_items(rows, limit=seeds_limit, only_safe=True)
    if not seeds:
        seeds = extract_seed_items(rows, limit=seeds_limit, only_safe=False)
    out_dir = default_runtime_dir(pure_jsonl, crc32=crc, out_base=out_base)
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "schema": "runtime_probe_config.libretro.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "pure_jsonl": str(pure_jsonl),
        "core_path": str(core_path),
        "rom_path": str(rom_path),
        "out_dir": str(out_dir),
        "max_frames": int(max_frames),
        "sample_every_frames": int(sample_every_frames),
        "max_bytes_per_capture": int(profile.get("max_bytes_per_capture", 192)),
        "default_terminators": profile.get("default_terminators", [0]),
        "autoplay_sequence": profile.get("autoplay_sequence", []),
        "seeds": seeds,
        "probe_hits_path": str(out_dir / f"{crc}_probe_hits.jsonl"),
    }


def write_probe_artifacts(payload: Dict[str, Any], project_root: Path) -> Dict[str, str]:
    out_dir = Path(payload["out_dir"])
    config_path = out_dir / f"{payload['rom_crc32']}_probe_config.libretro.json"
    script_path = out_dir / f"{payload['rom_crc32']}_probe_autoprobe.py"
    write_json(config_path, payload)
    script_path.write_text(_render_runner_script(config_path=config_path, project_root=project_root), encoding="utf-8")
    return {
        "probe_script_path": str(script_path),
        "probe_config_path": str(config_path),
        "probe_hits_path": str(payload["probe_hits_path"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera script AutoProbe para runtime libretro.")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--core-path", required=True, help="Caminho do core libretro (.dll/.so)")
    ap.add_argument("--rom-path", required=True, help="Caminho da ROM")
    ap.add_argument("--platform", default=None, help="Forca plataforma")
    ap.add_argument("--seeds", type=int, default=256, help="Quantidade maxima de seeds")
    ap.add_argument("--max-frames", type=int, default=18000, help="Frames maximos de probe")
    ap.add_argument("--sample-every-frames", type=int, default=6, help="Periodicidade de amostra")
    ap.add_argument("--out-base", default=None, help="Base de saida (default: .../out/<CRC>/runtime)")
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl nao encontrado: {pure_jsonl}")
    core_path = Path(args.core_path).expanduser().resolve()
    if not core_path.exists():
        raise SystemExit(f"[ERRO] core libretro nao encontrado: {core_path}")
    rom_path = Path(args.rom_path).expanduser().resolve()
    if not rom_path.exists():
        raise SystemExit(f"[ERRO] ROM nao encontrada: {rom_path}")

    payload = build_probe_payload(
        pure_jsonl=pure_jsonl,
        core_path=core_path,
        rom_path=rom_path,
        platform_hint=args.platform,
        seeds_limit=max(1, int(args.seeds)),
        max_frames=max(60, int(args.max_frames)),
        sample_every_frames=max(1, int(args.sample_every_frames)),
        out_base=Path(args.out_base).expanduser().resolve() if args.out_base else None,
    )
    artifacts = write_probe_artifacts(payload, project_root=Path(__file__).resolve().parents[2])
    print(json.dumps(artifacts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

