# -*- coding: utf-8 -*-
"""
Runner runtime (libretro) para scripts gerados de probe/trace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from runtime.emulator_runtime_host import EmulatorRuntimeHost, RetroJoypad


BUTTON_MAP = {
    "A": RetroJoypad.A,
    "B": RetroJoypad.B,
    "X": RetroJoypad.X,
    "Y": RetroJoypad.Y,
    "L": RetroJoypad.L,
    "R": RetroJoypad.R,
    "START": RetroJoypad.START,
    "SELECT": RetroJoypad.SELECT,
    "UP": RetroJoypad.UP,
    "DOWN": RetroJoypad.DOWN,
    "LEFT": RetroJoypad.LEFT,
    "RIGHT": RetroJoypad.RIGHT,
}


def _load_config(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(obj, dict):
        raise ValueError(f"config invalido: {path}")
    return obj


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if isinstance(meta, dict):
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _classify_context(frame: int) -> str:
    if frame < 1800:
        return "intro"
    if frame < 3600:
        return "menu"
    if frame < 9000:
        return "dialog"
    return "gameplay"


def _auto_step(host: EmulatorRuntimeHost, seq: List[Dict[str, Any]], frame: int) -> None:
    if not seq:
        return
    slot = (frame // 30) % len(seq)
    action = seq[slot]
    button = str(action.get("button", "")).strip().upper()
    frames = int(action.get("frames", 1) or 1)
    if frames <= 0:
        frames = 1
    btn = BUTTON_MAP.get(button)
    if btn is not None:
        host.press_button(btn, frames=1)


def _safe_terminators(value: Any) -> List[int]:
    if not isinstance(value, list):
        return [0]
    out: List[int] = []
    for item in value:
        try:
            out.append(int(item))
        except Exception:
            continue
    return out or [0]


def _bytes_to_row(
    frame: int,
    ptr_or_buf: str,
    raw: bytes,
    terminator: Optional[int],
    reason: str,
    ptr_register: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "frame": int(frame),
        "pc": None,
        "ptr_or_buf": str(ptr_or_buf),
        "raw_bytes_hex": raw.hex().upper(),
        "raw_len": int(len(raw)),
        "terminator": int(terminator) if terminator is not None else None,
        "context_tag": _classify_context(frame),
        "reason": str(reason),
        "ptr_register": str(ptr_register or ""),
    }


def _cut_until_terminator(data: bytes, terminators: List[int], max_len: int) -> Tuple[bytes, Optional[int]]:
    if max_len <= 0:
        max_len = len(data)
    if max_len <= 0:
        return b"", None
    out = bytearray()
    used_term: Optional[int] = None
    for b in data[:max_len]:
        out.append(int(b))
        if int(b) in terminators:
            used_term = int(b)
            break
    return bytes(out), used_term


def _seed_pattern(seed: Dict[str, Any]) -> bytes:
    raw_hex = str(seed.get("raw_bytes_hex", "") or "").strip().replace(" ", "")
    if raw_hex:
        try:
            src = bytes.fromhex(raw_hex)
        except Exception:
            src = b""
    else:
        src = b""
    if not src:
        return b""
    limit = int(seed.get("max_len_bytes", 8) or 8)
    if limit <= 0:
        limit = 8
    return src[: max(1, min(16, limit))]


def _scan_seeds_on_memory(
    frame: int,
    seeds: List[Dict[str, Any]],
    ram: bytes,
    vram: bytes,
    max_capture_len: int,
    terminators: List[int],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for seed in seeds:
        pat = _seed_pattern(seed)
        if len(pat) < 3:
            continue
        max_len = int(seed.get("raw_len", seed.get("max_len_bytes", 0)) or 0)
        if max_len <= 0:
            max_len = max_capture_len
        pos = ram.find(pat)
        if pos >= 0 and pos < len(ram):
            chunk = ram[pos : min(len(ram), pos + max_len)]
            raw, term = _cut_until_terminator(chunk, terminators, max_len)
            if raw:
                row = _bytes_to_row(
                    frame=frame,
                    ptr_or_buf=f"RAM:0x{pos:X}",
                    raw=raw,
                    terminator=term,
                    reason="seed_pattern_ram",
                )
                row["seed_id"] = seed.get("id")
                row["seed_key"] = seed.get("key")
                row["seed_offset"] = seed.get("rom_offset_hex")
                rows.append(row)

        pos_v = vram.find(pat)
        if pos_v >= 0 and pos_v < len(vram):
            chunk = vram[pos_v : min(len(vram), pos_v + max_len)]
            raw, term = _cut_until_terminator(chunk, terminators, max_len)
            if raw:
                row = _bytes_to_row(
                    frame=frame,
                    ptr_or_buf=f"VRAM:0x{pos_v:X}",
                    raw=raw,
                    terminator=term,
                    reason="seed_pattern_vram",
                )
                row["seed_id"] = seed.get("id")
                row["seed_key"] = seed.get("key")
                row["seed_offset"] = seed.get("rom_offset_hex")
                rows.append(row)
    return rows


def run_probe(config_path: Path) -> Dict[str, Any]:
    cfg = _load_config(config_path)
    core_path = Path(cfg.get("core_path", "")).expanduser().resolve()
    rom_path = Path(cfg.get("rom_path", "")).expanduser().resolve()
    out_jsonl = Path(cfg.get("probe_hits_path", "")).expanduser().resolve()

    if not core_path.exists():
        raise FileNotFoundError(f"libretro core nao encontrado: {core_path}")
    if not rom_path.exists():
        raise FileNotFoundError(f"ROM nao encontrada: {rom_path}")

    max_frames = int(cfg.get("max_frames", 18000) or 18000)
    sample_every = int(cfg.get("sample_every_frames", 6) or 6)
    max_capture_len = int(cfg.get("max_bytes_per_capture", 192) or 192)
    seeds = list(cfg.get("seeds", []) or [])
    autoplay = list(cfg.get("autoplay_sequence", []) or [])
    terminators = _safe_terminators(cfg.get("default_terminators", [0]))

    rows: List[Dict[str, Any]] = []
    meta = {
        "type": "meta",
        "schema": "runtime_probe_hits.v1",
        "rom_crc32": cfg.get("rom_crc32"),
        "rom_size": cfg.get("rom_size"),
        "platform": cfg.get("platform"),
        "generator": "libretro_runtime_runner.run_probe",
        "seeds_total": len(seeds),
    }

    with EmulatorRuntimeHost(str(core_path), str(rom_path)) as host:
        if not host.is_running:
            raise RuntimeError("Falha ao iniciar runtime host libretro.")
        for frame in range(max_frames):
            _auto_step(host, autoplay, frame)
            host.step_frame()
            if sample_every > 1 and (frame % sample_every) != 0:
                continue
            ram = host.get_ram()
            vram = host.get_vram()
            if not ram and not vram:
                continue
            rows.extend(
                _scan_seeds_on_memory(
                    frame=frame,
                    seeds=seeds,
                    ram=ram or b"",
                    vram=vram or b"",
                    max_capture_len=max_capture_len,
                    terminators=terminators,
                )
            )

    _write_jsonl(out_jsonl, rows, meta=meta)
    return {
        "probe_hits_path": str(out_jsonl),
        "rows_total": int(len(rows)),
        "schema": "runtime_probe_hits.v1",
    }


def _extract_addr_from_ptr_or_buf(raw: str) -> Optional[Tuple[str, int]]:
    txt = str(raw or "").strip()
    if not txt:
        return None
    if ":" not in txt:
        return None
    pref, _, addr = txt.partition(":")
    addr_val = None
    addr = addr.strip()
    if addr.lower().startswith("0x"):
        try:
            addr_val = int(addr, 16)
        except Exception:
            addr_val = None
    else:
        try:
            addr_val = int(addr)
        except Exception:
            addr_val = None
    if addr_val is None:
        return None
    return pref.strip().upper(), int(addr_val)


def run_trace(config_path: Path) -> Dict[str, Any]:
    cfg = _load_config(config_path)
    core_path = Path(cfg.get("core_path", "")).expanduser().resolve()
    rom_path = Path(cfg.get("rom_path", "")).expanduser().resolve()
    out_jsonl = Path(cfg.get("runtime_trace_path", "")).expanduser().resolve()

    if not core_path.exists():
        raise FileNotFoundError(f"libretro core nao encontrado: {core_path}")
    if not rom_path.exists():
        raise FileNotFoundError(f"ROM nao encontrada: {rom_path}")

    max_frames = int(cfg.get("max_frames", 24000) or 24000)
    sample_every = int(cfg.get("sample_every_frames", 8) or 8)
    max_capture_len = int(cfg.get("max_bytes_per_capture", 224) or 224)
    autoplay = list(cfg.get("autoplay_sequence", []) or [])
    seeds = list(cfg.get("seed_fallback", []) or [])
    buffer_candidates = list(cfg.get("buffer_candidates", []) or [])
    terminators = _safe_terminators(cfg.get("default_terminators", [0]))

    rows: List[Dict[str, Any]] = []
    meta = {
        "type": "meta",
        "schema": "runtime_trace.v1",
        "rom_crc32": cfg.get("rom_crc32"),
        "rom_size": cfg.get("rom_size"),
        "platform": cfg.get("platform"),
        "generator": "libretro_runtime_runner.run_trace",
        "buffer_candidates_total": len(buffer_candidates),
        "seed_fallback_total": len(seeds),
    }

    with EmulatorRuntimeHost(str(core_path), str(rom_path)) as host:
        if not host.is_running:
            raise RuntimeError("Falha ao iniciar runtime host libretro.")
        for frame in range(max_frames):
            _auto_step(host, autoplay, frame)
            host.step_frame()
            if sample_every > 1 and (frame % sample_every) != 0:
                continue
            ram = host.get_ram() or b""
            vram = host.get_vram() or b""

            # Buffers candidatos do hook profile (se disponíveis)
            for cand in buffer_candidates:
                ptr_txt = str(cand.get("ptr_or_buf", "") or "")
                parsed = _extract_addr_from_ptr_or_buf(ptr_txt)
                if not parsed:
                    continue
                domain, addr = parsed
                source = ram if "RAM" in domain else vram
                if not source or addr < 0 or addr >= len(source):
                    continue
                chunk = source[addr : min(len(source), addr + max_capture_len)]
                raw, term = _cut_until_terminator(chunk, terminators, max_capture_len)
                if not raw:
                    continue
                rows.append(
                    _bytes_to_row(
                        frame=frame,
                        ptr_or_buf=ptr_txt,
                        raw=raw,
                        terminator=term,
                        reason="buffer_candidate",
                    )
                )

            # Fallback por seed (sem scan cego)
            rows.extend(
                _scan_seeds_on_memory(
                    frame=frame,
                    seeds=seeds,
                    ram=ram,
                    vram=vram,
                    max_capture_len=max_capture_len,
                    terminators=terminators,
                )
            )

    _write_jsonl(out_jsonl, rows, meta=meta)
    return {
        "runtime_trace_path": str(out_jsonl),
        "rows_total": int(len(rows)),
        "schema": "runtime_trace.v1",
    }

