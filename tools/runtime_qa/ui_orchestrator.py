#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestrador único do Runtime QA para a UI.

Fluxo:
1) AutoProbe
2) Hook Profile
3) Trace + Autoplay
4) RuntimeQA (report/proof)

Sem scan cego: usa apenas seeds do pure_text + trace runtime real.
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:
    from .analyze_probe_hits import build_profile
    from .common import (
        compute_crc32,
        infer_platform_from_path,
        iter_jsonl,
        load_json,
        parse_int,
        write_jsonl,
    )
    from .generate_probe_bizhawk import build_probe_payload, write_probe_artifacts
    from .generate_probe_libretro import (
        build_probe_payload as build_probe_payload_libretro,
        write_probe_artifacts as write_probe_artifacts_libretro,
    )
    from .generate_trace_autoplay_bizhawk import (
        build_trace_payload,
        write_trace_artifacts,
    )
    from .generate_dyn_capture_bizhawk import (
        build_dyn_capture_payload,
        write_dyn_capture_artifacts,
    )
    from .generate_trace_autoplay_libretro import (
        build_trace_payload as build_trace_payload_libretro,
        write_trace_artifacts as write_trace_artifacts_libretro,
    )
    from .dyn_text_pipeline import (
        discover_static_only_safe_by_offset,
        process_dynamic_capture,
    )
    from ..ocr_screenshots.glyph_matcher import run_ocr_screenshot_pipeline
    from .runtime_qa_step import run_runtime_qa
except ImportError:  # pragma: no cover
    from analyze_probe_hits import build_profile  # type: ignore
    from common import (  # type: ignore
        compute_crc32,
        infer_platform_from_path,
        iter_jsonl,
        load_json,
        parse_int,
        write_jsonl,
    )
    from generate_probe_bizhawk import (  # type: ignore
        build_probe_payload,
        write_probe_artifacts,
    )
    from generate_probe_libretro import (  # type: ignore
        build_probe_payload as build_probe_payload_libretro,
        write_probe_artifacts as write_probe_artifacts_libretro,
    )
    from generate_trace_autoplay_bizhawk import (  # type: ignore
        build_trace_payload,
        write_trace_artifacts,
    )
    from generate_dyn_capture_bizhawk import (  # type: ignore
        build_dyn_capture_payload,
        write_dyn_capture_artifacts,
    )
    from generate_trace_autoplay_libretro import (  # type: ignore
        build_trace_payload as build_trace_payload_libretro,
        write_trace_artifacts as write_trace_artifacts_libretro,
    )
    from dyn_text_pipeline import (  # type: ignore
        discover_static_only_safe_by_offset,
        process_dynamic_capture,
    )
    tools_root = Path(__file__).resolve().parents[1]
    if str(tools_root) not in sys.path:
        sys.path.insert(0, str(tools_root))
    from ocr_screenshots.glyph_matcher import run_ocr_screenshot_pipeline  # type: ignore
    from runtime_qa_step import run_runtime_qa  # type: ignore


RUNTIME_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "S0_intro_advance": {
        "label": "S0_intro_advance -> Intro / avançar caixas",
        "autoplay": [{"button": "START", "frames": 2}, {"button": "A", "frames": 2}],
    },
    "S1_menu_cycle": {
        "label": "S1_menu_cycle -> Menus / status / inventário",
        "autoplay": [
            {"button": "START", "frames": 2},
            {"button": "DOWN", "frames": 2},
            {"button": "UP", "frames": 2},
            {"button": "B", "frames": 2},
        ],
    },
    "S2_npc_talk_walk": {
        "label": "S2_npc_talk_walk -> NPC / talk + caminhada",
        "autoplay": [
            {"button": "RIGHT", "frames": 2},
            {"button": "RIGHT", "frames": 2},
            {"button": "A", "frames": 2},
            {"button": "LEFT", "frames": 2},
            {"button": "A", "frames": 2},
        ],
    },
    "S3_shop_buy_sell": {
        "label": "S3_shop_buy_sell -> Loja / comprar e vender",
        "autoplay": [
            {"button": "A", "frames": 2},
            {"button": "DOWN", "frames": 2},
            {"button": "A", "frames": 2},
            {"button": "B", "frames": 2},
        ],
    },
    "S4_battle_messages": {
        "label": "S4_battle_messages -> Batalha / mensagens do sistema",
        "autoplay": [
            {"button": "A", "frames": 2},
            {"button": "A", "frames": 2},
            {"button": "B", "frames": 2},
        ],
    },
    "S5_long_text_boxes": {
        "label": "S5_long_text_boxes -> Caixas longas / páginas",
        "autoplay": [
            {"button": "A", "frames": 2},
            {"button": "A", "frames": 2},
            {"button": "A", "frames": 2},
            {"button": "B", "frames": 2},
        ],
    },
}

OCR_CONSOLES = [
    "nes",
    "snes",
    "megadrive",
    "master_system",
    "gba",
    "ps1",
    "n64",
]


def _log(logger: Callable[[str], None], message: str) -> None:
    logger(str(message))


def _default_logger(message: str) -> None:
    print(message, flush=True)


class RuntimeQAError(RuntimeError):
    """Erro amigável do orquestrador."""


def _format_duration(value_s: float) -> str:
    secs = max(0, int(round(float(value_s))))
    mins, sec = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}h{mins:02d}m{sec:02d}s"
    if mins > 0:
        return f"{mins}m{sec:02d}s"
    return f"{sec}s"


def _parse_scenarios(raw: str | Iterable[str] | None) -> List[str]:
    if raw is None:
        return list(RUNTIME_SCENARIOS.keys())
    if isinstance(raw, str):
        items = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        items = [str(x).strip() for x in raw if str(x).strip()]
    out: List[str] = []
    for item in items:
        if item in RUNTIME_SCENARIOS and item not in out:
            out.append(item)
    return out or list(RUNTIME_SCENARIOS.keys())


def _spawn_reader_thread(pipe, q: "queue.Queue[Optional[str]]") -> threading.Thread:
    def _reader() -> None:
        try:
            for line in iter(pipe.readline, ""):
                q.put(line.rstrip("\r\n"))
        finally:
            q.put(None)

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return t


def _run_process(
    cmd: List[str],
    timeout_s: int,
    logger: Callable[[str], None],
    progress_label: str = "",
) -> Dict[str, Any]:
    start = time.time()
    last_heartbeat = start
    heartbeat_s = 15
    label = str(progress_label or Path(str(cmd[0] if cmd else "processo")).name)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as exc:
        raise RuntimeQAError(f"Falha ao iniciar processo: {exc}") from exc

    q: "queue.Queue[Optional[str]]" = queue.Queue()
    reader_done = False
    _spawn_reader_thread(proc.stdout, q)  # type: ignore[arg-type]
    lines: List[str] = []
    timed_out = False

    while True:
        now = time.time()
        if timeout_s > 0 and (now - start) > timeout_s:
            timed_out = True
            break
        try:
            item = q.get(timeout=0.15)
            if item is None:
                reader_done = True
            elif item:
                lines.append(item)
                _log(logger, item)
        except queue.Empty:
            pass

        if (now - last_heartbeat) >= heartbeat_s:
            elapsed = now - start
            if timeout_s > 0:
                remaining = max(0.0, float(timeout_s) - elapsed)
                pct = min(99, int((elapsed / float(max(1, timeout_s))) * 100.0))
                _log(
                    logger,
                    (
                        f"Runtime QA: {label} em execução... "
                        f"decorrido={_format_duration(elapsed)} | "
                        f"ETA máx restante={_format_duration(remaining)} | "
                        f"timeout={pct}%"
                    ),
                )
            else:
                _log(
                    logger,
                    f"Runtime QA: {label} em execução... decorrido={_format_duration(elapsed)}",
                )
            last_heartbeat = now

        if proc.poll() is not None and reader_done:
            break

    if timed_out:
        elapsed = time.time() - start
        _log(
            logger,
            f"Runtime QA: {label} atingiu timeout após {_format_duration(elapsed)}.",
        )
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return {"returncode": -9, "timed_out": True, "lines": lines}

    # drena resto
    try:
        tail = proc.stdout.read() if proc.stdout else ""
    except Exception:
        tail = ""
    if tail:
        for chunk in str(tail).splitlines():
            if chunk.strip():
                lines.append(chunk)
                _log(logger, chunk)

    elapsed = time.time() - start
    _log(logger, f"Runtime QA: {label} finalizado em {_format_duration(elapsed)}.")
    return {"returncode": int(proc.returncode or 0), "timed_out": False, "lines": lines}


def _wait_file_nonempty(path: Path, timeout_s: int = 8) -> bool:
    end = time.time() + max(1, int(timeout_s))
    while time.time() < end:
        if path.exists():
            try:
                if path.stat().st_size > 0:
                    return True
            except Exception:
                pass
        time.sleep(0.2)
    return False


def _read_trace_rows(trace_path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    meta: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for obj in iter_jsonl(trace_path):
        if obj.get("type") == "meta":
            meta = dict(obj)
            continue
        if isinstance(obj, dict):
            rows.append(dict(obj))
    return meta, rows


def _merge_runtime_traces(
    crc32: str,
    rom_size: int,
    platform: str,
    scenario_traces: List[Dict[str, Any]],
    merged_path: Path,
) -> Dict[str, Any]:
    seen = set()
    merged_rows: List[Dict[str, Any]] = []
    total_rows = 0
    for item in scenario_traces:
        scen_id = str(item.get("scenario_id", "") or "")
        trace_path = Path(item.get("trace_path", ""))
        if not trace_path.exists():
            continue
        _, rows = _read_trace_rows(trace_path)
        total_rows += len(rows)
        for row in rows:
            ptr = str(row.get("ptr_or_buf", "") or "")
            raw = str(row.get("raw_bytes_hex", "") or "").upper()
            key = (ptr, raw)
            if key in seen:
                continue
            seen.add(key)
            merged = dict(row)
            merged["scenario_id"] = scen_id
            merged_rows.append(merged)

    merged_rows.sort(
        key=lambda r: (
            parse_int(r.get("frame"), default=1 << 30) or (1 << 30),
            str(r.get("ptr_or_buf", "")),
            str(r.get("raw_bytes_hex", "")),
        )
    )
    meta = {
        "type": "meta",
        "schema": "runtime_trace_merged.v1",
        "rom_crc32": str(crc32).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "scenarios_total": int(len(scenario_traces)),
        "rows_input_total": int(total_rows),
        "rows_unique_total": int(len(merged_rows)),
    }
    write_jsonl(merged_path, merged_rows, meta=meta)
    return {"rows_input_total": int(total_rows), "rows_unique_total": int(len(merged_rows))}


def _deep_find_int(obj: Any, candidate_keys: Iterable[str]) -> Optional[int]:
    keys = set(candidate_keys)
    stack: List[Any] = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in keys:
                    iv = parse_int(v, default=None)
                    if iv is not None:
                        return int(iv)
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return None


def _metric_from_report_text(path: Optional[Path], candidates: Iterable[str]) -> Optional[int]:
    if path is None or not path.exists():
        return None
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    for key in candidates:
        patt = rf"{key}\s*[:=]\s*(\d+)"
        m = None
        try:
            import re

            m = re.search(patt, txt, flags=re.IGNORECASE)
        except Exception:
            m = None
        if m:
            try:
                return int(m.group(1))
            except Exception:
                continue
    return None


def _extract_gate_metrics(
    proof_json: Optional[Path],
    report_txt: Optional[Path],
) -> Dict[str, int]:
    proof_obj = load_json(proof_json, {}) if proof_json else {}
    term = _deep_find_int(
        proof_obj,
        ("terminator_missing_count", "terminator_missing"),
    )
    mismatch = _deep_find_int(
        proof_obj,
        ("rom_vs_translated_mismatch_count", "rom_vs_translated_mismatch"),
    )
    if term is None:
        term = _metric_from_report_text(
            report_txt, ("terminator_missing_count", "terminator_missing")
        )
    if mismatch is None:
        mismatch = _metric_from_report_text(
            report_txt,
            ("rom_vs_translated_mismatch_count", "rom_vs_translated_mismatch"),
        )
    # Gate estrito: sem evidência explícita não fecha PASS.
    if term is None:
        term = 1
    if mismatch is None:
        mismatch = 1
    return {
        "terminator_missing": int(term or 0),
        "rom_vs_translated_mismatch": int(mismatch or 0),
    }

def _run_probe_bizhawk(
    pure_jsonl: Path,
    runtime_dir: Path,
    platform: str,
    timeout_probe_s: int,
    emuhawk_path: Path,
    rom_path: Path,
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    out_base = runtime_dir.parent.parent
    payload = build_probe_payload(
        pure_jsonl=pure_jsonl,
        platform_hint=platform,
        seeds_limit=256,
        sample_every_frames=6,
        max_frames=max(600, int(timeout_probe_s * 60)),
        out_base=out_base,
    )
    # Força caminhos determinísticos dentro do runtime_dir.
    payload["out_dir"] = str(runtime_dir)
    payload["probe_script_path"] = str(runtime_dir / f"{payload['rom_crc32']}_probe_autoprobe.lua")
    payload["probe_hits_path"] = str(runtime_dir / f"{payload['rom_crc32']}_probe_hits.jsonl")
    artifacts = write_probe_artifacts(payload)
    probe_script = Path(artifacts["probe_script_path"])
    probe_hits = Path(artifacts["probe_hits_path"])
    cmd = [str(emuhawk_path), f"--lua={probe_script}", str(rom_path)]
    run = _run_process(
        cmd=cmd,
        timeout_s=int(timeout_probe_s),
        logger=logger,
        progress_label="PROBE (BizHawk)",
    )
    timed_out = bool(run.get("timed_out"))
    partial_ready = _wait_file_nonempty(probe_hits, timeout_s=8)
    if timed_out and partial_ready:
        _log(
            logger,
            "Runtime QA: PROBE atingiu timeout, mas gerou probe_hits válido; seguindo com perfil parcial.",
        )
    elif timed_out:
        raise RuntimeQAError(
            "Timeout no PROBE: o emulador não encerrou no prazo (verifique client.exit no Lua)."
        )
    if int(run["returncode"]) != 0 and not timed_out:
        raise RuntimeQAError("Emulador retornou erro no PROBE.")
    if not partial_ready:
        raise RuntimeQAError("PROBE não gerou probe_hits.jsonl válido.")
    return {
        "probe_script_path": str(probe_script),
        "probe_hits_path": str(probe_hits),
        "probe_config_path": str(artifacts.get("probe_config_path", "")),
        "timed_out": bool(timed_out),
    }


def _run_trace_bizhawk(
    pure_jsonl: Path,
    hook_profile: Path,
    runtime_dir: Path,
    platform: str,
    timeout_trace_s: int,
    emuhawk_path: Path,
    rom_path: Path,
    trace_suffix: str,
    autoplay_override: Optional[List[Dict[str, Any]]],
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    out_base = runtime_dir.parent.parent
    payload = build_trace_payload(
        pure_jsonl=pure_jsonl,
        hook_profile_path=hook_profile,
        platform_hint=platform,
        max_watch_pcs=24,
        seeds_fallback=96,
        sample_every_frames=8,
        max_frames=max(900, int(timeout_trace_s * 60)),
        trace_suffix=trace_suffix,
        out_base=out_base,
    )
    payload["out_dir"] = str(runtime_dir)
    suffix = str(trace_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix
    payload["runtime_trace_script_path"] = str(
        runtime_dir / f"{payload['rom_crc32']}_runtime_trace_autoplay{suffix}.lua"
    )
    payload["runtime_trace_path"] = str(runtime_dir / f"{payload['rom_crc32']}_runtime_trace{suffix}.jsonl")
    if autoplay_override:
        payload["autoplay_sequence"] = autoplay_override
    artifacts = write_trace_artifacts(payload)
    trace_script = Path(artifacts["runtime_trace_script_path"])
    trace_out = Path(artifacts["runtime_trace_path"])
    cmd = [str(emuhawk_path), f"--lua={trace_script}", str(rom_path)]
    run = _run_process(
        cmd=cmd,
        timeout_s=int(timeout_trace_s),
        logger=logger,
        progress_label="TRACE (BizHawk)",
    )
    timed_out = bool(run.get("timed_out"))
    partial_ready = _wait_file_nonempty(trace_out, timeout_s=8)
    if timed_out and partial_ready:
        _log(
            logger,
            "Runtime QA: TRACE atingiu timeout, mas gerou runtime_trace válido; seguindo com trace parcial.",
        )
    elif timed_out:
        raise RuntimeQAError(
            "Timeout no TRACE: o emulador não encerrou no prazo (verifique client.exit no Lua)."
        )
    if int(run["returncode"]) != 0 and not timed_out:
        raise RuntimeQAError("Emulador retornou erro no TRACE.")
    if not partial_ready:
        raise RuntimeQAError("TRACE não gerou runtime_trace.jsonl válido.")
    return {
        "runtime_trace_script_path": str(trace_script),
        "runtime_trace_path": str(trace_out),
        "runtime_trace_config_path": str(artifacts.get("runtime_trace_config_path", "")),
        "timed_out": bool(timed_out),
    }


def _run_dyn_capture_bizhawk(
    pure_jsonl: Path,
    runtime_dir: Path,
    platform: str,
    timeout_trace_s: int,
    emuhawk_path: Path,
    rom_path: Path,
    trace_suffix: str,
    fontmap_json: Optional[Path],
    input_explorer_enabled: bool,
    savestate_bfs_enabled: bool,
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    out_base = runtime_dir.parent.parent
    # Modo agressivo: captura mais estados por rodada para reduzir platô de cobertura.
    dyn_aggressive = bool(input_explorer_enabled or savestate_bfs_enabled)
    # Captura dinâmica pode rodar abaixo de 45 FPS dependendo do custo por frame.
    # Aumenta orçamento de frames/timeout quando modo agressivo está ligado.
    dyn_max_frames = max(3600, int(timeout_trace_s * (45 if dyn_aggressive else 35)))
    dyn_timeout_s = max(int(timeout_trace_s), int(dyn_max_frames / 18) + 90)
    # Menor intervalo => mais snapshots (maior chance de achar linhas raras).
    dyn_sample_every = 3 if dyn_aggressive else 2
    dyn_savestate_depth = 3 if savestate_bfs_enabled else 2
    dyn_savestate_branch = 360 if savestate_bfs_enabled else 480
    dyn_savestate_slots = 8 if savestate_bfs_enabled else 6
    dyn_seed_slots = [1, 2, 3] if savestate_bfs_enabled else []
    payload = build_dyn_capture_payload(
        pure_jsonl=pure_jsonl,
        platform_hint=platform,
        fontmap_json=fontmap_json,
        max_frames=dyn_max_frames,
        sample_every_frames=dyn_sample_every,
        input_explorer_enabled=bool(input_explorer_enabled),
        input_explorer_switch_frames=360,
        savestate_bfs_enabled=bool(savestate_bfs_enabled),
        savestate_bfs_depth=dyn_savestate_depth,
        savestate_branch_frames=dyn_savestate_branch,
        savestate_slot_base=1,
        savestate_slot_count=dyn_savestate_slots,
        savestate_seed_slots=dyn_seed_slots,
        trace_suffix=trace_suffix,
        out_base=out_base,
    )
    if dyn_aggressive:
        # Captura mais candidatos de name/pattern por frame para maximizar cobertura.
        payload["capture_top_candidates"] = max(6, int(payload.get("capture_top_candidates", 2)))
        # Expande varredura vertical para capturar linhas fora da janela principal (menus/caixas ocultas).
        try:
            cur_rows = int(payload.get("tile_rows", 28))
        except Exception:
            cur_rows = 28
        payload["tile_rows"] = max(cur_rows, min(40, cur_rows + 4))
    payload["out_dir"] = str(runtime_dir)
    suffix = str(trace_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix
    payload["dyn_capture_script_path"] = str(runtime_dir / f"{payload['rom_crc32']}_dyn_capture{suffix}.lua")
    payload["dyn_text_log_path"] = str(runtime_dir / f"{payload['rom_crc32']}_dyn_text_log_raw{suffix}.jsonl")
    artifacts = write_dyn_capture_artifacts(payload)
    dyn_script = Path(artifacts["dyn_capture_script_path"])
    dyn_out = Path(artifacts["dyn_text_log_path"])
    cmd = [str(emuhawk_path), f"--lua={dyn_script}", str(rom_path)]
    run = _run_process(
        cmd=cmd,
        timeout_s=dyn_timeout_s,
        logger=logger,
        progress_label="DYN CAPTURE (BizHawk)",
    )
    timed_out = bool(run.get("timed_out"))
    partial_ready = _wait_file_nonempty(dyn_out, timeout_s=8)
    if timed_out and partial_ready:
        _log(
            logger,
            "Runtime QA: DYN-CAPTURE atingiu timeout, mas gerou log parcial válido; seguindo com pós-processamento.",
        )
    elif timed_out:
        raise RuntimeQAError(
            "Timeout no DYN-CAPTURE: o emulador não encerrou no prazo (verifique client.exit no Lua)."
        )
    if int(run["returncode"]) != 0 and not timed_out:
        raise RuntimeQAError("Emulador retornou erro no DYN-CAPTURE.")
    if not partial_ready:
        raise RuntimeQAError("DYN-CAPTURE não gerou dyn_text_log_raw.jsonl válido.")
    return {
        "dyn_capture_script_path": str(dyn_script),
        "dyn_text_log_path": str(dyn_out),
        "dyn_capture_config_path": str(artifacts.get("dyn_capture_config_path", "")),
        "timed_out": bool(timed_out),
    }


def _postprocess_dyn_capture(
    *,
    crc32: str,
    pure_jsonl: Path,
    runtime_dyn_dir: Path,
    dyn_raw_path: Path,
    runtime_dyn_fontmap_json: Optional[Path],
    runtime_static_only_safe_by_offset: Optional[Path],
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    runtime_dyn_dir = runtime_dyn_dir.expanduser().resolve()
    dyn_raw_path = dyn_raw_path.expanduser().resolve()
    static_path = runtime_static_only_safe_by_offset
    if static_path is None:
        static_path = discover_static_only_safe_by_offset(
            crc32=crc32,
            pure_jsonl=pure_jsonl,
            runtime_dir=runtime_dyn_dir,
        )
    if static_path is None:
        _log(
            logger,
            "Runtime QA: static_only_safe_by_offset não encontrado; diff de cobertura dinâmica será pulado.",
        )

    dyn_capture_result = process_dynamic_capture(
        dyn_log_input_path=dyn_raw_path,
        out_dir=runtime_dyn_dir,
        crc32=crc32,
        static_only_safe_by_offset=static_path,
        fontmap_path=runtime_dyn_fontmap_json,
        bootstrap_enabled=True,
    )
    _log(logger, f"Runtime QA: postprocess finished -> {runtime_dyn_dir}")
    return dyn_capture_result


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _update_best_dyn_coverage(
    *,
    runtime_dyn_dir: Path,
    crc32: str,
    coverage: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persiste o melhor progresso dinâmico já observado para evitar regressões
    visuais quando uma rodada parcial captura menos texto.
    """
    runtime_dyn_dir = runtime_dyn_dir.expanduser().resolve()
    runtime_dyn_dir.mkdir(parents=True, exist_ok=True)
    best_path = runtime_dyn_dir / f"{str(crc32).upper()}_coverage_best.json"

    current_capture = _to_float(coverage.get("capture_progress_percent"), 0.0)
    current_strict = _to_float(coverage.get("coverage_percent"), 0.0)

    existing: Dict[str, Any] = {}
    if best_path.exists():
        try:
            raw = json.loads(best_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(raw, dict):
                existing = raw
        except Exception:
            existing = {}

    best_capture_prev = _to_float(existing.get("capture_progress_percent"), 0.0)
    best_strict_prev = _to_float(existing.get("coverage_percent"), 0.0)

    if (current_capture > best_capture_prev) or (
        abs(current_capture - best_capture_prev) < 1e-9 and current_strict > best_strict_prev
    ):
        best_payload = {
            "rom_crc32": str(crc32).upper(),
            "capture_progress_percent": float(round(current_capture, 4)),
            "coverage_percent": float(round(current_strict, 4)),
            "updated_at_epoch_s": int(time.time()),
            "source": "runtime_dyn_capture",
        }
        try:
            best_path.write_text(
                json.dumps(best_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        best_capture = best_payload["capture_progress_percent"]
        best_strict = best_payload["coverage_percent"]
    else:
        best_capture = best_capture_prev
        best_strict = best_strict_prev

    coverage["best_capture_progress_percent"] = float(round(best_capture, 4))
    coverage["best_coverage_percent"] = float(round(best_strict, 4))
    coverage["coverage_best_path"] = str(best_path)
    return coverage


def _merge_dyn_logs(
    crc32: str,
    rom_size: int,
    platform: str,
    dyn_logs: List[Path],
    merged_path: Path,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    total_rows = 0
    dedup_rows = 0
    seen_keys: set[Tuple[Any, ...]] = set()
    for src in dyn_logs:
        if not src.exists():
            continue
        for obj in iter_jsonl(src):
            if obj.get("type") == "meta":
                continue
            if not isinstance(obj, dict):
                continue
            frame_val = parse_int(obj.get("frame"), default=-1)
            line_idx_val = parse_int(obj.get("line_idx"), default=-1)
            line_text = str(obj.get("line", obj.get("text", "")) or "")
            key = (
                int(frame_val if frame_val is not None else -1),
                int(line_idx_val if line_idx_val is not None else -1),
                str(obj.get("scene_hash", "") or ""),
                str(obj.get("pattern_base", "") or ""),
                str(obj.get("nametable_base", "") or ""),
                str(obj.get("tile_row_hex", "") or ""),
                line_text,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            rows.append(dict(obj))
            total_rows += 1
            dedup_rows += 1

    rows.sort(
        key=lambda r: (
            parse_int(r.get("frame"), default=1 << 30) or (1 << 30),
            str(r.get("scene_hash", "")),
            str(r.get("line", r.get("text", ""))),
        )
    )
    meta = {
        "type": "meta",
        "schema": "runtime_dyn_capture_merged.v1",
        "rom_crc32": str(crc32).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "rows_input_total": int(total_rows),
        "rows_merged_total": int(len(rows)),
        "rows_dedup_total": int(dedup_rows),
        "sources_total": int(len(dyn_logs)),
    }
    write_jsonl(merged_path, rows, meta=meta)
    return {
        "rows_input_total": int(total_rows),
        "rows_merged_total": int(len(rows)),
        "rows_dedup_total": int(dedup_rows),
    }


def _prepare_cumulative_dyn_log(
    *,
    runtime_dyn_dir: Path,
    dyn_raw_path: Path,
    crc32: str,
    rom_size: int,
    platform: str,
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    """
    Mantém histórico cumulativo da captura dinâmica para somar progresso entre rodadas.
    """
    runtime_dyn_dir = runtime_dyn_dir.expanduser().resolve()
    dyn_raw_path = dyn_raw_path.expanduser().resolve()
    history_path = runtime_dyn_dir / f"{str(crc32).upper()}_dyn_text_log_raw_history.jsonl"
    tmp_path = runtime_dyn_dir / f"{str(crc32).upper()}_dyn_text_log_raw_history_tmp.jsonl"
    donor_logs: List[Path] = []

    if not dyn_raw_path.exists() or dyn_raw_path.stat().st_size <= 0:
        return {"path": str(dyn_raw_path), "history_updated": False}

    # Reaproveita históricos paralelos da mesma ROM (ex.: variações de runtime),
    # evitando perder cobertura já capturada em outras rodadas.
    try:
        rom_root = runtime_dyn_dir.parent.parent
        crc_up = str(crc32).upper()
        donor_candidates: List[Path] = []
        for pat in (
            f"{crc_up}_dyn_text_log_raw_history.jsonl",
            f"{crc_up}_dyn_text_log_raw_dyn.jsonl",
        ):
            donor_candidates.extend(rom_root.rglob(pat))
        seen_paths = {history_path.resolve(), dyn_raw_path.resolve()}
        for cand in donor_candidates:
            cpath = cand.expanduser().resolve()
            if cpath in seen_paths:
                continue
            if not cpath.exists() or cpath.stat().st_size <= 0:
                continue
            if cpath not in donor_logs:
                donor_logs.append(cpath)
        if donor_logs:
            _log(
                logger,
                f"Runtime QA: consolidação de históricos detectou {len(donor_logs)} fonte(s) extra(s).",
            )
    except Exception:
        donor_logs = []

    if not history_path.exists() or history_path.stat().st_size <= 0:
        try:
            if donor_logs:
                stats = _merge_dyn_logs(
                    crc32=crc32,
                    rom_size=rom_size,
                    platform=platform,
                    dyn_logs=[dyn_raw_path] + donor_logs,
                    merged_path=history_path,
                )
                _log(
                    logger,
                    "Runtime QA: histórico dinâmico criado (com consolidação) "
                    f"(input={int(stats.get('rows_input_total', 0))}, merged={int(stats.get('rows_merged_total', 0))}).",
                )
                return {
                    "path": str(history_path),
                    "history_updated": True,
                    "rows_input_total": int(stats.get("rows_input_total", 0)),
                    "rows_merged_total": int(stats.get("rows_merged_total", 0)),
                    "rows_dedup_total": int(stats.get("rows_dedup_total", 0)),
                }
            shutil.copyfile(str(dyn_raw_path), str(history_path))
            _log(logger, f"Runtime QA: histórico dinâmico criado -> {history_path}")
            return {
                "path": str(history_path),
                "history_updated": True,
                "rows_input_total": 0,
                "rows_merged_total": 0,
                "rows_dedup_total": 0,
            }
        except Exception as exc:
            _log(logger, f"Runtime QA: falha ao criar histórico dinâmico ({exc}); usando log atual.")
            return {"path": str(dyn_raw_path), "history_updated": False}

    try:
        stats = _merge_dyn_logs(
            crc32=crc32,
            rom_size=rom_size,
            platform=platform,
            dyn_logs=[history_path, dyn_raw_path] + donor_logs,
            merged_path=tmp_path,
        )
        try:
            if history_path.exists():
                history_path.unlink()
        except Exception:
            pass
        tmp_path.replace(history_path)
        _log(
            logger,
            "Runtime QA: histórico dinâmico atualizado "
            f"(input={int(stats.get('rows_input_total', 0))}, merged={int(stats.get('rows_merged_total', 0))}, dedup={int(stats.get('rows_dedup_total', 0))}).",
        )
        return {
            "path": str(history_path),
            "history_updated": True,
            "rows_input_total": int(stats.get("rows_input_total", 0)),
            "rows_merged_total": int(stats.get("rows_merged_total", 0)),
            "rows_dedup_total": int(stats.get("rows_dedup_total", 0)),
        }
    except Exception as exc:
        _log(logger, f"Runtime QA: falha no merge cumulativo dinâmico ({exc}); usando log atual.")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return {"path": str(dyn_raw_path), "history_updated": False}


def _estimate_total_eta_s(
    *,
    mode_norm: str,
    runtime_dyn_only: bool,
    runtime_dyn_enabled: bool,
    runner_norm: str,
    timeout_probe_s: int,
    timeout_trace_s: int,
    runtime_scenarios_enabled: List[str],
    max_iterations: int,
) -> int:
    total = 0
    if runtime_dyn_only:
        # Aproximação conservadora para dyn capture.
        total += max(int(timeout_trace_s), 120)
        return int(max(1, total))

    total += max(1, int(timeout_probe_s))
    if mode_norm == "max":
        scen_count = max(1, int(len(runtime_scenarios_enabled or [])))
        total += max(1, int(timeout_trace_s)) * scen_count * max(1, int(max_iterations))
    else:
        total += max(1, int(timeout_trace_s))

    if runtime_dyn_enabled and runner_norm == "bizhawk":
        total += max(1, int(timeout_trace_s))

    # Pós-processamento / merge / runtime_qa_step.
    total += 20
    return int(max(1, total))


def _run_probe_libretro(
    pure_jsonl: Path,
    runtime_dir: Path,
    platform: str,
    timeout_probe_s: int,
    rom_path: Path,
    libretro_core: Path,
    libretro_runner: Optional[str],
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    out_base = runtime_dir.parent.parent
    payload = build_probe_payload_libretro(
        pure_jsonl=pure_jsonl,
        core_path=libretro_core,
        rom_path=rom_path,
        platform_hint=platform,
        seeds_limit=256,
        max_frames=max(600, int(timeout_probe_s * 60)),
        sample_every_frames=6,
        out_base=out_base,
    )
    payload["out_dir"] = str(runtime_dir)
    payload["probe_hits_path"] = str(runtime_dir / f"{payload['rom_crc32']}_probe_hits.jsonl")
    artifacts = write_probe_artifacts_libretro(payload, project_root=Path(__file__).resolve().parents[2])
    probe_script = Path(artifacts["probe_script_path"])
    probe_hits = Path(artifacts["probe_hits_path"])
    runner_cmd = [libretro_runner] if libretro_runner else [sys.executable]
    cmd = runner_cmd + [str(probe_script)]
    run = _run_process(
        cmd=cmd,
        timeout_s=int(timeout_probe_s),
        logger=logger,
        progress_label="PROBE (Libretro)",
    )
    if run["timed_out"]:
        raise RuntimeQAError("Timeout no PROBE (libretro).")
    if int(run["returncode"]) != 0:
        raise RuntimeQAError("Runner libretro retornou erro no PROBE.")
    if not _wait_file_nonempty(probe_hits, timeout_s=8):
        raise RuntimeQAError("PROBE (libretro) não gerou probe_hits.jsonl válido.")
    return {
        "probe_script_path": str(probe_script),
        "probe_hits_path": str(probe_hits),
        "probe_config_path": str(artifacts.get("probe_config_path", "")),
    }


def _run_trace_libretro(
    pure_jsonl: Path,
    hook_profile: Path,
    runtime_dir: Path,
    platform: str,
    timeout_trace_s: int,
    rom_path: Path,
    libretro_core: Path,
    libretro_runner: Optional[str],
    trace_suffix: str,
    autoplay_override: Optional[List[Dict[str, Any]]],
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    out_base = runtime_dir.parent.parent
    payload = build_trace_payload_libretro(
        pure_jsonl=pure_jsonl,
        hook_profile_path=hook_profile,
        core_path=libretro_core,
        rom_path=rom_path,
        platform_hint=platform,
        max_frames=max(900, int(timeout_trace_s * 60)),
        sample_every_frames=8,
        seeds_fallback=96,
        out_base=out_base,
    )
    suffix = str(trace_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix
    payload["out_dir"] = str(runtime_dir)
    payload["runtime_trace_path"] = str(runtime_dir / f"{payload['rom_crc32']}_runtime_trace{suffix}.jsonl")
    if autoplay_override:
        payload["autoplay_sequence"] = autoplay_override
    artifacts = write_trace_artifacts_libretro(payload, project_root=Path(__file__).resolve().parents[2])
    trace_script = Path(artifacts["runtime_trace_script_path"])
    trace_out = Path(artifacts["runtime_trace_path"])
    runner_cmd = [libretro_runner] if libretro_runner else [sys.executable]
    cmd = runner_cmd + [str(trace_script)]
    run = _run_process(
        cmd=cmd,
        timeout_s=int(timeout_trace_s),
        logger=logger,
        progress_label="TRACE (Libretro)",
    )
    if run["timed_out"]:
        raise RuntimeQAError("Timeout no TRACE (libretro).")
    if int(run["returncode"]) != 0:
        raise RuntimeQAError("Runner libretro retornou erro no TRACE.")
    if not _wait_file_nonempty(trace_out, timeout_s=8):
        raise RuntimeQAError("TRACE (libretro) não gerou runtime_trace.jsonl válido.")
    return {
        "runtime_trace_script_path": str(trace_script),
        "runtime_trace_path": str(trace_out),
        "runtime_trace_config_path": str(artifacts.get("runtime_trace_config_path", "")),
    }


def run_orchestrator(
    mode: str,
    rom_path: Path,
    pure_jsonl: Path,
    translated_jsonl: Path,
    mapping_json: Path,
    runtime_dir: Path,
    report_txt: Optional[Path],
    proof_json: Optional[Path],
    report_json: Optional[Path],
    path_emuhawk: Optional[Path],
    libretro_runner: Optional[str],
    libretro_core: Optional[Path],
    timeout_probe_s: int,
    timeout_trace_s: int,
    runtime_scenarios_enabled: List[str],
    max_iterations: int,
    plateau_rounds: int,
    runner_mode: str = "auto",
    platform_hint: Optional[str] = None,
    runtime_dyn_enabled: bool = True,
    runtime_dyn_only: bool = False,
    runtime_dyn_fontmap_json: Optional[Path] = None,
    runtime_dyn_input_explorer: bool = False,
    runtime_dyn_savestate_bfs: bool = False,
    runtime_static_only_safe_by_offset: Optional[Path] = None,
    logger: Callable[[str], None] = _default_logger,
) -> Dict[str, Any]:
    runtime_dir = runtime_dir.expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_dyn_dir = (runtime_dir / "2_runtime_dyn").expanduser().resolve()
    rom_path = rom_path.expanduser().resolve()
    pure_jsonl = pure_jsonl.expanduser().resolve()
    translated_jsonl = translated_jsonl.expanduser().resolve()
    mapping_json = mapping_json.expanduser().resolve()
    report_txt = report_txt.expanduser().resolve() if report_txt else None
    proof_json = proof_json.expanduser().resolve() if proof_json else None
    report_json = report_json.expanduser().resolve() if report_json else None
    runtime_dyn_fontmap_json = (
        runtime_dyn_fontmap_json.expanduser().resolve() if runtime_dyn_fontmap_json else None
    )
    runtime_static_only_safe_by_offset = (
        runtime_static_only_safe_by_offset.expanduser().resolve()
        if runtime_static_only_safe_by_offset
        else None
    )

    if not rom_path.exists():
        raise RuntimeQAError(f"ROM não encontrada: {rom_path}")
    if not pure_jsonl.exists():
        raise RuntimeQAError(f"pure_text.jsonl não encontrado: {pure_jsonl}")
    if not runtime_dyn_only and not translated_jsonl.exists():
        raise RuntimeQAError(f"translated.jsonl não encontrado: {translated_jsonl}")
    if not runtime_dyn_only and not mapping_json.exists():
        raise RuntimeQAError(f"reinsertion_mapping.json não encontrado: {mapping_json}")
    if runtime_dyn_fontmap_json is not None and not runtime_dyn_fontmap_json.exists():
        _log(logger, f"Runtime QA: fontmap não encontrado ({runtime_dyn_fontmap_json}), seguindo sem fontmap.")
        runtime_dyn_fontmap_json = None

    platform = str(platform_hint or infer_platform_from_path(str(rom_path), fallback="master_system"))
    crc32 = compute_crc32(rom_path)
    rom_size = int(rom_path.stat().st_size)
    mode_norm = str(mode or "auto").strip().lower()
    if mode_norm not in {"auto", "max"}:
        mode_norm = "auto"

    runner_norm = str(runner_mode or "auto").strip().lower()
    if runner_norm == "auto":
        runner_norm = "bizhawk" if path_emuhawk and path_emuhawk.exists() else "libretro"

    if runner_norm == "bizhawk":
        if not path_emuhawk or not path_emuhawk.exists():
            raise RuntimeQAError("Runtime QA: path_emuhawk inválido ou não configurado.")
    else:
        if not libretro_core or not libretro_core.exists():
            raise RuntimeQAError("Runtime QA: libretro_core_path inválido ou não configurado.")

    eta_total_s = _estimate_total_eta_s(
        mode_norm=mode_norm,
        runtime_dyn_only=bool(runtime_dyn_only),
        runtime_dyn_enabled=bool(runtime_dyn_enabled),
        runner_norm=runner_norm,
        timeout_probe_s=int(timeout_probe_s),
        timeout_trace_s=int(timeout_trace_s),
        runtime_scenarios_enabled=list(runtime_scenarios_enabled or []),
        max_iterations=int(max_iterations),
    )
    _log(
        logger,
        (
            "Runtime QA: estimativa inicial de conclusão ~"
            f"{_format_duration(eta_total_s)} (pode terminar antes)."
        ),
    )

    if runtime_dyn_only:
        if runner_norm != "bizhawk":
            raise RuntimeQAError("Runtime Dyn (BizHawk) exige runner BizHawk com path_emuhawk válido.")
        runtime_dyn_dir.mkdir(parents=True, exist_ok=True)
        _log(logger, "Runtime QA: modo runtime-dyn-only habilitado (sem AutoProbe).")
        _log(logger, f"Runtime QA: artefatos runtime-dyn -> {runtime_dyn_dir}")

        dyn_capture_warning: Optional[str] = None
        dyn_capture_result: Dict[str, Any] = {}
        dyn_data: Dict[str, Any] = {}
        try:
            _log(logger, "Runtime QA: executando captura dinâmica de tilemap/VRAM…")
            dyn_data = _run_dyn_capture_bizhawk(
                pure_jsonl=pure_jsonl,
                runtime_dir=runtime_dyn_dir,
                platform=platform,
                timeout_trace_s=timeout_trace_s,
                emuhawk_path=path_emuhawk,  # type: ignore[arg-type]
                rom_path=rom_path,
                trace_suffix="dyn",
                fontmap_json=runtime_dyn_fontmap_json,
                input_explorer_enabled=bool(runtime_dyn_input_explorer),
                savestate_bfs_enabled=bool(runtime_dyn_savestate_bfs),
                logger=logger,
            )
            dyn_raw = Path(dyn_data["dyn_text_log_path"])
            _log(logger, f"Runtime QA: dyn capture finished -> {dyn_raw.resolve()}")
            dyn_log_for_post = dyn_raw
            cumulative = _prepare_cumulative_dyn_log(
                runtime_dyn_dir=runtime_dyn_dir,
                dyn_raw_path=dyn_raw,
                crc32=crc32,
                rom_size=rom_size,
                platform=platform,
                logger=logger,
            )
            cum_path_raw = str(cumulative.get("path", "") or "").strip()
            if cum_path_raw:
                dyn_log_for_post = Path(cum_path_raw).expanduser().resolve()
            if bool(dyn_data.get("timed_out")):
                dyn_capture_warning = (
                    "DYN-CAPTURE atingiu timeout e usou log parcial; cobertura pode ficar incompleta."
                )
                _log(logger, f"Runtime QA: {dyn_capture_warning}")
            dyn_capture_result = _postprocess_dyn_capture(
                crc32=crc32,
                pure_jsonl=pure_jsonl,
                runtime_dyn_dir=runtime_dyn_dir,
                dyn_raw_path=dyn_log_for_post,
                runtime_dyn_fontmap_json=runtime_dyn_fontmap_json,
                runtime_static_only_safe_by_offset=runtime_static_only_safe_by_offset,
                logger=logger,
            )
            dyn_capture_result["dyn_log_input_path"] = str(dyn_log_for_post)
            dyn_capture_result["dyn_log_raw_path"] = str(dyn_raw)
            cov_raw = dict(dyn_capture_result.get("coverage") or {})
            cov_pure = dict(dyn_capture_result.get("coverage_pure") or {})
            cov = dict(cov_pure or cov_raw or {})
            if cov_pure and cov_raw:
                dyn_capture_result["coverage_raw"] = cov_raw
                dyn_capture_result["coverage"] = cov
            if cov:
                cov = _update_best_dyn_coverage(
                    runtime_dyn_dir=runtime_dyn_dir,
                    crc32=crc32,
                    coverage=cov,
                )
                dyn_capture_result["coverage"] = cov
                _log(
                    logger,
                    "Runtime QA: cobertura dinâmica (pura) "
                    f"captura={float(cov.get('capture_progress_percent', 0.0)):.2f}% "
                    f"(melhor={float(cov.get('best_capture_progress_percent', cov.get('capture_progress_percent', 0.0))):.2f}%) | "
                    f"strict={float(cov.get('coverage_percent', 0.0)):.2f}%",
                )
        except Exception as exc:
            dyn_capture_warning = f"Falha na captura dinâmica: {exc}"
            _log(logger, f"Runtime QA: {dyn_capture_warning}")

        _log(logger, "Runtime QA: modo runtime-dyn-only concluído.")
        status = "PASS" if (not dyn_capture_warning and dyn_capture_result) else "WARN"
        return {
            "status": status,
            "mode": "Runtime Dyn (BizHawk)",
            "rom_crc32": crc32,
            "rom_size": rom_size,
            "platform": platform,
            "runtime_missing": 0,
            "english_residual": 0,
            "terminator_missing": 0,
            "rom_vs_translated_mismatch": 0,
            "total_scenarios_executed": 0,
            "total_unique_texts": 0,
            "new_unique_texts_last_pass": 0,
            "runtime_dir": str(runtime_dir),
            "runtime_dyn_dir": str(runtime_dyn_dir),
            "runtime_dyn_warning": dyn_capture_warning,
            "runtime_dyn_summary": dyn_capture_result,
            "artifacts": {
                "runtime_dyn_dir": str(runtime_dyn_dir),
                "dyn_capture_script_path": str(dyn_data.get("dyn_capture_script_path", "")),
                "dyn_capture_config_path": str(dyn_data.get("dyn_capture_config_path", "")),
                "dyn_text_log": str(
                    dyn_capture_result.get("dyn_text_log_path")
                    or dyn_data.get("dyn_text_log_path", "")
                ),
                "dyn_text_unique": str(dyn_capture_result.get("dyn_text_unique_path", "")),
                "dyn_fontmap_bootstrap": str(dyn_capture_result.get("fontmap_bootstrap_path", "")),
                "dyn_unknown_glyphs_jsonl": str(dyn_capture_result.get("unknown_glyphs_jsonl_path", "")),
                "dyn_unknown_glyphs_png": str(dyn_capture_result.get("unknown_glyphs_png_path", "")),
                "coverage_diff_report": str(
                    dyn_capture_result.get("coverage", {}).get("coverage_diff_report_path", "")
                ),
                "coverage_missing_from_runtime": str(
                    dyn_capture_result.get("coverage", {}).get("missing_from_runtime_path", "")
                ),
                "coverage_missing_from_static": str(
                    dyn_capture_result.get("coverage", {}).get("missing_from_static_path", "")
                ),
            },
            "scenario_runs": [],
            "merge_stats": {},
            "runtime_step_summary": {},
        }

    _log(logger, "Runtime QA: validando configuração do emulador…")
    _log(logger, "Runtime QA: gerando PROBE (seeds do pure_text)…")
    _log(logger, "Runtime QA: executando emulador (PROBE)…")

    if runner_norm == "bizhawk":
        probe_data = _run_probe_bizhawk(
            pure_jsonl=pure_jsonl,
            runtime_dir=runtime_dir,
            platform=platform,
            timeout_probe_s=timeout_probe_s,
            emuhawk_path=path_emuhawk,  # type: ignore[arg-type]
            rom_path=rom_path,
            logger=logger,
        )
    else:
        probe_data = _run_probe_libretro(
            pure_jsonl=pure_jsonl,
            runtime_dir=runtime_dir,
            platform=platform,
            timeout_probe_s=timeout_probe_s,
            rom_path=rom_path,
            libretro_core=libretro_core,  # type: ignore[arg-type]
            libretro_runner=libretro_runner,
            logger=logger,
        )
    if bool(probe_data.get("timed_out")):
        _log(
            logger,
            "Runtime QA: PROBE usou saída parcial por timeout; a qualidade do hook profile pode cair.",
        )

    _log(logger, "Runtime QA: analisando PROBE hits e construindo hook profile…")
    hook_profile_path = build_profile(
        hits_path=Path(probe_data["probe_hits_path"]),
        out_path=runtime_dir / f"{crc32}_runtime_hook_profile.json",
        platform_hint=platform,
    )
    if not hook_profile_path.exists():
        raise RuntimeQAError("Falha ao gerar runtime_hook_profile.")

    _log(logger, "Runtime QA: gerando TRACE + AUTOPLAY…")
    trace_paths: List[Path] = []
    scenario_runs: List[Dict[str, Any]] = []
    total_scenarios_executed = 0
    new_unique_last_pass = 0
    total_unique_texts = 0
    dyn_capture_result: Dict[str, Any] = {}
    dyn_capture_warning: Optional[str] = None

    if mode_norm == "auto":
        _log(logger, "Runtime QA: executando emulador (TRACE)…")
        if runner_norm == "bizhawk":
            trace_data = _run_trace_bizhawk(
                pure_jsonl=pure_jsonl,
                hook_profile=hook_profile_path,
                runtime_dir=runtime_dir,
                platform=platform,
                timeout_trace_s=timeout_trace_s,
                emuhawk_path=path_emuhawk,  # type: ignore[arg-type]
                rom_path=rom_path,
                trace_suffix="",
                autoplay_override=None,
                logger=logger,
            )
        else:
            trace_data = _run_trace_libretro(
                pure_jsonl=pure_jsonl,
                hook_profile=hook_profile_path,
                runtime_dir=runtime_dir,
                platform=platform,
                timeout_trace_s=timeout_trace_s,
                rom_path=rom_path,
                libretro_core=libretro_core,  # type: ignore[arg-type]
                libretro_runner=libretro_runner,
                trace_suffix="",
                autoplay_override=None,
                logger=logger,
            )
            trace_path = Path(trace_data["runtime_trace_path"])
            if bool(trace_data.get("timed_out")):
                _log(
                    logger,
                    "Runtime QA: TRACE usou saída parcial por timeout; cobertura runtime pode ficar incompleta.",
                )
            trace_paths.append(trace_path)
        _, rows = _read_trace_rows(trace_path)
        total_unique_texts = len({(str(r.get("ptr_or_buf", "")), str(r.get("raw_bytes_hex", ""))) for r in rows})
        new_unique_last_pass = total_unique_texts
    else:
        _log(logger, "Runtime QA: executando emulador (TRACE)…")
        enabled_scenarios = _parse_scenarios(runtime_scenarios_enabled)
        unique_seen = set()
        plateau = 0
        current_iter = 0
        while current_iter < max(1, int(max_iterations)) and plateau < max(1, int(plateau_rounds)):
            current_iter += 1
            _log(
                logger,
                (
                    f"Runtime QA: iteração {current_iter}/{max(1, int(max_iterations))} "
                    f"(plateau={plateau}/{max(1, int(plateau_rounds))})"
                ),
            )
            new_unique_in_pass = 0
            for scen_id in enabled_scenarios:
                scen_cfg = RUNTIME_SCENARIOS.get(scen_id, {})
                scen_suffix = f"{scen_id}_p{current_iter}"
                autoplay = scen_cfg.get("autoplay", [])
                if runner_norm == "bizhawk":
                    trace_data = _run_trace_bizhawk(
                        pure_jsonl=pure_jsonl,
                        hook_profile=hook_profile_path,
                        runtime_dir=runtime_dir,
                        platform=platform,
                        timeout_trace_s=timeout_trace_s,
                        emuhawk_path=path_emuhawk,  # type: ignore[arg-type]
                        rom_path=rom_path,
                        trace_suffix=scen_suffix,
                        autoplay_override=autoplay,
                        logger=logger,
                    )
                else:
                    trace_data = _run_trace_libretro(
                        pure_jsonl=pure_jsonl,
                        hook_profile=hook_profile_path,
                        runtime_dir=runtime_dir,
                        platform=platform,
                        timeout_trace_s=timeout_trace_s,
                        rom_path=rom_path,
                        libretro_core=libretro_core,  # type: ignore[arg-type]
                        libretro_runner=libretro_runner,
                        trace_suffix=scen_suffix,
                        autoplay_override=autoplay,
                        logger=logger,
                    )
                trace_path = Path(trace_data["runtime_trace_path"])
                if bool(trace_data.get("timed_out")):
                    _log(
                        logger,
                        f"Runtime QA: TRACE parcial no cenário {scen_id} (timeout com arquivo válido).",
                    )
                trace_paths.append(trace_path)
                total_scenarios_executed += 1
                _, rows = _read_trace_rows(trace_path)
                unique_local = {(str(r.get("ptr_or_buf", "")), str(r.get("raw_bytes_hex", ""))) for r in rows}
                before = len(unique_seen)
                unique_seen.update(unique_local)
                new_now = len(unique_seen) - before
                new_unique_in_pass += max(0, int(new_now))
                scenario_runs.append(
                    {
                        "scenario_id": scen_id,
                        "scenario_label": scen_cfg.get("label", scen_id),
                        "trace_path": str(trace_path),
                        "rows_total": int(len(rows)),
                        "new_unique_texts": int(new_now),
                    }
                )
            total_unique_texts = len(unique_seen)
            new_unique_last_pass = int(new_unique_in_pass)
            if new_unique_in_pass == 0:
                plateau += 1
            else:
                plateau = 0

    if not trace_paths:
        raise RuntimeQAError("Nenhum runtime_trace foi gerado.")

    if mode_norm == "max":
        merged_trace = runtime_dir / f"{crc32}_runtime_trace_merged.jsonl"
        merge_stats = _merge_runtime_traces(
            crc32=crc32,
            rom_size=rom_size,
            platform=platform,
            scenario_traces=scenario_runs,
            merged_path=merged_trace,
        )
        runtime_trace_for_step = merged_trace
    else:
        merged_trace = None
        merge_stats = {}
        runtime_trace_for_step = trace_paths[0]

    if runtime_dyn_enabled:
        runtime_dyn_dir.mkdir(parents=True, exist_ok=True)
        _log(logger, f"Runtime QA: artefatos runtime-dyn -> {runtime_dyn_dir}")
        if runner_norm != "bizhawk":
            dyn_capture_warning = "Captura dinâmica VRAM/NameTable disponível apenas com runner BizHawk."
            _log(logger, f"Runtime QA: {dyn_capture_warning}")
        else:
            try:
                _log(logger, "Runtime QA: executando captura dinâmica de tilemap/VRAM…")
                dyn_data = _run_dyn_capture_bizhawk(
                    pure_jsonl=pure_jsonl,
                    runtime_dir=runtime_dyn_dir,
                    platform=platform,
                    timeout_trace_s=timeout_trace_s,
                    emuhawk_path=path_emuhawk,  # type: ignore[arg-type]
                    rom_path=rom_path,
                    trace_suffix="dynmax" if mode_norm == "max" else "dyn",
                    fontmap_json=runtime_dyn_fontmap_json,
                    input_explorer_enabled=bool(runtime_dyn_input_explorer),
                    savestate_bfs_enabled=bool(runtime_dyn_savestate_bfs),
                    logger=logger,
                )
                dyn_raw = Path(dyn_data["dyn_text_log_path"])
                _log(logger, f"Runtime QA: dyn capture finished -> {dyn_raw.resolve()}")
                dyn_log_for_post = dyn_raw
                cumulative = _prepare_cumulative_dyn_log(
                    runtime_dyn_dir=runtime_dyn_dir,
                    dyn_raw_path=dyn_raw,
                    crc32=crc32,
                    rom_size=rom_size,
                    platform=platform,
                    logger=logger,
                )
                cum_path_raw = str(cumulative.get("path", "") or "").strip()
                if cum_path_raw:
                    dyn_log_for_post = Path(cum_path_raw).expanduser().resolve()
                if bool(dyn_data.get("timed_out")):
                    dyn_capture_warning = (
                        "DYN-CAPTURE atingiu timeout e usou log parcial; cobertura pode ficar incompleta."
                    )
                    _log(logger, f"Runtime QA: {dyn_capture_warning}")
                dyn_capture_result = _postprocess_dyn_capture(
                    crc32=crc32,
                    pure_jsonl=pure_jsonl,
                    runtime_dyn_dir=runtime_dyn_dir,
                    dyn_raw_path=dyn_log_for_post,
                    runtime_dyn_fontmap_json=runtime_dyn_fontmap_json,
                    runtime_static_only_safe_by_offset=runtime_static_only_safe_by_offset,
                    logger=logger,
                )
                dyn_capture_result["dyn_log_input_path"] = str(dyn_log_for_post)
                dyn_capture_result["dyn_log_raw_path"] = str(dyn_raw)
                cov_raw = dict(dyn_capture_result.get("coverage") or {})
                cov_pure = dict(dyn_capture_result.get("coverage_pure") or {})
                cov = dict(cov_pure or cov_raw or {})
                if cov_pure and cov_raw:
                    dyn_capture_result["coverage_raw"] = cov_raw
                    dyn_capture_result["coverage"] = cov
                if cov:
                    cov = _update_best_dyn_coverage(
                        runtime_dyn_dir=runtime_dyn_dir,
                        crc32=crc32,
                        coverage=cov,
                    )
                    dyn_capture_result["coverage"] = cov
                    _log(
                        logger,
                        "Runtime QA: cobertura dinâmica (pura) "
                        f"captura={float(cov.get('capture_progress_percent', 0.0)):.2f}% "
                        f"(melhor={float(cov.get('best_capture_progress_percent', cov.get('capture_progress_percent', 0.0))):.2f}%) | "
                        f"strict={float(cov.get('coverage_percent', 0.0)):.2f}%",
                    )
            except Exception as exc:
                dyn_capture_warning = f"Falha na captura dinâmica: {exc}"
                _log(logger, f"Runtime QA: {dyn_capture_warning}")

    _log(logger, "Runtime QA: consolidando RuntimeQA (report/proof)…")
    step = run_runtime_qa(
        runtime_trace_path=runtime_trace_for_step,
        translated_jsonl=translated_jsonl,
        mapping_json=mapping_json,
        out_dir=runtime_dir,
        proof_json=proof_json,
        report_txt=report_txt,
        report_json=report_json,
        force_crc=crc32,
        force_size=rom_size,
        force_platform=platform,
        inject_artifacts=True,
    )
    summary = step.get("summary", {}) if isinstance(step, dict) else {}
    runtime_missing = int(
        parse_int(
            summary.get("runtime_missing_displayed_text_count", summary.get("missing_displayed_text_count")),
            default=0,
        )
        or 0
    )
    runtime_english = int(
        parse_int(
            summary.get("runtime_english_residual_count", summary.get("runtime_displayed_english_residual_count")),
            default=0,
        )
        or 0
    )
    gate_metrics = _extract_gate_metrics(proof_json=proof_json, report_txt=report_txt)
    terminator_missing = int(gate_metrics.get("terminator_missing", 0))
    mismatch = int(gate_metrics.get("rom_vs_translated_mismatch", 0))
    is_pass = bool(
        runtime_missing == 0
        and runtime_english == 0
        and terminator_missing == 0
        and mismatch == 0
    )

    _log(logger, "Runtime QA: concluído.")

    result = {
        "status": "PASS" if is_pass else "FAIL",
        "mode": "Cobertura máxima (cenários)" if mode_norm == "max" else "Auto (rápido)",
        "rom_crc32": crc32,
        "rom_size": rom_size,
        "platform": platform,
        "runtime_missing": runtime_missing,
        "english_residual": runtime_english,
        "terminator_missing": terminator_missing,
        "rom_vs_translated_mismatch": mismatch,
        "total_scenarios_executed": int(total_scenarios_executed if mode_norm == "max" else 1),
        "total_unique_texts": int(total_unique_texts),
        "new_unique_texts_last_pass": int(new_unique_last_pass),
        "runtime_dir": str(runtime_dir),
        "runtime_dyn_dir": str(runtime_dyn_dir),
        "runtime_dyn_warning": dyn_capture_warning,
        "runtime_dyn_summary": dyn_capture_result,
        "artifacts": {
            "runtime_dyn_dir": str(runtime_dyn_dir),
            "probe_hits": str(probe_data.get("probe_hits_path", "")),
            "hook_profile": str(hook_profile_path),
            "runtime_trace": str(runtime_trace_for_step),
            "runtime_trace_merged": str(merged_trace) if merged_trace else None,
            "runtime_displayed_text_trace": str(step.get("runtime_displayed_text_trace")),
            "runtime_missing_displayed_text": str(step.get("runtime_missing_displayed_text")),
            "runtime_coverage_summary": str(step.get("runtime_coverage_summary")),
            "dyn_text_log": str(dyn_capture_result.get("dyn_text_log_path", "")),
            "dyn_text_unique": str(dyn_capture_result.get("dyn_text_unique_path", "")),
            "dyn_fontmap_bootstrap": str(dyn_capture_result.get("fontmap_bootstrap_path", "")),
            "dyn_unknown_glyphs_jsonl": str(dyn_capture_result.get("unknown_glyphs_jsonl_path", "")),
            "dyn_unknown_glyphs_png": str(dyn_capture_result.get("unknown_glyphs_png_path", "")),
            "coverage_diff_report": str(dyn_capture_result.get("coverage", {}).get("coverage_diff_report_path", "")),
            "coverage_missing_from_runtime": str(dyn_capture_result.get("coverage", {}).get("missing_from_runtime_path", "")),
            "coverage_missing_from_static": str(dyn_capture_result.get("coverage", {}).get("missing_from_static_path", "")),
            "proof_injected": step.get("proof_injected"),
            "report_injected": step.get("report_injected"),
            "report_json_injected": step.get("report_json_injected"),
        },
        "scenario_runs": scenario_runs,
        "merge_stats": merge_stats,
        "runtime_step_summary": summary,
    }
    return result


def _run_ocr_screenshots_mode(
    *,
    rom_arg: str,
    input_folder: Path,
    runtime_dir: Optional[Path],
    console: str,
    min_confidence: float,
    min_votes: int,
    update_fontmap: bool,
    logger: Callable[[str], None],
) -> Dict[str, Any]:
    rom_txt = str(rom_arg or "").strip()
    rom_crc_hint: Optional[str] = None
    rom_path = Path(rom_txt).expanduser()
    if re.fullmatch(r"[0-9A-Fa-f]{8}", rom_txt):
        rom_crc_hint = rom_txt.upper()
        rom_path = Path("")
    elif rom_path.exists() and rom_path.is_file():
        rom_crc_hint = compute_crc32(rom_path)

    input_dir = input_folder.expanduser().resolve()
    if runtime_dir is not None:
        rt_dir = runtime_dir.expanduser().resolve()
    else:
        rt_dir = (input_dir.parent / "runtime").resolve()
    rt_dir.mkdir(parents=True, exist_ok=True)

    _log(
        logger,
        (
            "Runtime QA OCR: iniciando pipeline screenshots "
            f"(console={console}, min_conf={float(min_confidence):.3f}, min_votes={int(min_votes)})"
        ),
    )
    result = run_ocr_screenshot_pipeline(
        input_folder=input_dir,
        runtime_dir=rt_dir,
        console=console,
        min_confidence=float(min_confidence),
        min_votes=max(1, int(min_votes)),
        update_fontmap=bool(update_fontmap),
        rom_crc32=rom_crc_hint,
        logger=logger,
    )
    _log(logger, "Runtime QA OCR: pipeline concluido.")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Orquestrador UI: Runtime QA (Auto ou Cobertura máxima).")
    ap.add_argument("--mode", default="auto", choices=["auto", "max"], help="Modo de execução")
    ap.add_argument("--runner", default="auto", choices=["auto", "bizhawk", "libretro"], help="Runner de emulador")
    ap.add_argument("--rom", required=True, help="Caminho da ROM ou CRC32 (modo OCR)")
    ap.add_argument("--pure-jsonl", default=None, help="Caminho do {CRC32}_pure_text.jsonl")
    ap.add_argument("--translated-jsonl", default=None, help="Caminho do {CRC32}_translated*.jsonl")
    ap.add_argument("--mapping-json", default=None, help="Caminho do {CRC32}_reinsertion_mapping.json")
    ap.add_argument("--runtime-dir", default=None, help="Diretorio de saida runtime")
    ap.add_argument("--report-txt", default=None, help="Caminho do {CRC32}_report.txt")
    ap.add_argument("--proof-json", default=None, help="Caminho do {CRC32}_proof.json")
    ap.add_argument("--report-json", default=None, help="Caminho do {CRC32}_reinsertion_report.json")
    ap.add_argument("--platform", default=None, help="Força plataforma")
    ap.add_argument("--path-emuhawk", default=None, help="Caminho do EmuHawk.exe")
    ap.add_argument("--runner-libretro", default=None, help="Runner libretro (opcional)")
    ap.add_argument("--libretro-core-path", default=None, help="Core libretro (.dll/.so)")
    ap.add_argument("--timeout-probe-s", type=int, default=120, help="Timeout do PROBE")
    ap.add_argument("--timeout-trace-s", type=int, default=180, help="Timeout do TRACE")
    ap.add_argument(
        "--runtime-scenarios-enabled",
        default=",".join(RUNTIME_SCENARIOS.keys()),
        help="Lista CSV de cenários para modo max",
    )
    ap.add_argument("--max-iterations", type=int, default=3, help="Iterações máximas no modo max")
    ap.add_argument("--plateau-rounds", type=int, default=2, help="Parada por platô no modo max")
    ap.add_argument(
        "--runtime-dyn-enabled",
        type=int,
        default=1,
        help="1 habilita captura dinâmica VRAM/NameTable (BizHawk).",
    )
    ap.add_argument(
        "--runtime-dyn-only",
        type=int,
        default=0,
        help="1 executa apenas captura dinâmica (sem AutoProbe/TRACE/Runtime QA final).",
    )
    ap.add_argument(
        "--runtime-dyn-fontmap-json",
        default=None,
        help="JSON tile->char para reconstrução dinâmica.",
    )
    ap.add_argument(
        "--runtime-dyn-input-explorer",
        type=int,
        default=1,
        help="1 habilita explorador de inputs por roteiro.",
    )
    ap.add_argument(
        "--runtime-dyn-savestate-bfs",
        type=int,
        default=1,
        help="1 habilita BFS de savestates (experimental).",
    )
    ap.add_argument(
        "--runtime-static-only-safe-by-offset",
        default=None,
        help="Arquivo estático *_only_safe_text_by_offset para diff de cobertura.",
    )
    ap.add_argument(
        "--ocr-screenshots",
        action="store_true",
        help="Ativa pipeline OCR por screenshots para mapear glyphs desconhecidos.",
    )
    ap.add_argument(
        "--input-folder",
        default=None,
        help="Pasta com screenshots (PNG/JPEG) para OCR.",
    )
    ap.add_argument(
        "--console",
        default=None,
        choices=OCR_CONSOLES,
        help="Console alvo do OCR screenshots.",
    )
    ap.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Confianca minima por deteccao OCR (0.0-1.0).",
    )
    ap.add_argument(
        "--min-votes",
        type=int,
        default=3,
        help="Minimo de votos para confirmar glyph_hash->char.",
    )
    ap.add_argument(
        "--update-fontmap",
        action="store_true",
        help="Confirma que o resultado OCR deve ser usado como fontmap enhanced.",
    )
    args = ap.parse_args()

    try:
        if bool(args.ocr_screenshots):
            if not args.input_folder:
                raise RuntimeQAError("Modo --ocr-screenshots exige --input-folder.")
            if not args.console:
                raise RuntimeQAError("Modo --ocr-screenshots exige --console.")
            result = _run_ocr_screenshots_mode(
                rom_arg=str(args.rom or ""),
                input_folder=Path(args.input_folder),
                runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
                console=str(args.console or "").strip(),
                min_confidence=max(0.0, min(1.0, float(args.min_confidence))),
                min_votes=max(1, int(args.min_votes)),
                update_fontmap=bool(args.update_fontmap),
                logger=_default_logger,
            )
        else:
            runtime_dyn_only = bool(int(args.runtime_dyn_only or 0))
            if not args.pure_jsonl:
                raise RuntimeQAError("Modo Runtime QA exige --pure-jsonl.")
            if not args.runtime_dir:
                raise RuntimeQAError("Modo Runtime QA exige --runtime-dir.")
            if not runtime_dyn_only and not args.translated_jsonl:
                raise RuntimeQAError("Modo Runtime QA exige --translated-jsonl (ou use --runtime-dyn-only 1).")
            if not runtime_dyn_only and not args.mapping_json:
                raise RuntimeQAError("Modo Runtime QA exige --mapping-json (ou use --runtime-dyn-only 1).")

            translated_jsonl = Path(args.translated_jsonl) if args.translated_jsonl else Path(args.pure_jsonl)
            mapping_json = Path(args.mapping_json) if args.mapping_json else Path(args.pure_jsonl)

            result = run_orchestrator(
                mode=str(args.mode or "auto"),
                rom_path=Path(args.rom),
                pure_jsonl=Path(args.pure_jsonl),
                translated_jsonl=translated_jsonl,
                mapping_json=mapping_json,
                runtime_dir=Path(args.runtime_dir),
                report_txt=Path(args.report_txt) if args.report_txt else None,
                proof_json=Path(args.proof_json) if args.proof_json else None,
                report_json=Path(args.report_json) if args.report_json else None,
                path_emuhawk=Path(args.path_emuhawk) if args.path_emuhawk else None,
                libretro_runner=str(args.runner_libretro).strip() if args.runner_libretro else None,
                libretro_core=Path(args.libretro_core_path) if args.libretro_core_path else None,
                timeout_probe_s=max(30, int(args.timeout_probe_s)),
                timeout_trace_s=max(30, int(args.timeout_trace_s)),
                runtime_scenarios_enabled=_parse_scenarios(args.runtime_scenarios_enabled),
                max_iterations=max(1, int(args.max_iterations)),
                plateau_rounds=max(1, int(args.plateau_rounds)),
                runner_mode=str(args.runner or "auto"),
                platform_hint=str(args.platform or "").strip() or None,
                runtime_dyn_enabled=bool(int(args.runtime_dyn_enabled or 0)),
                runtime_dyn_only=runtime_dyn_only,
                runtime_dyn_fontmap_json=Path(args.runtime_dyn_fontmap_json) if args.runtime_dyn_fontmap_json else None,
                runtime_dyn_input_explorer=bool(int(args.runtime_dyn_input_explorer or 0)),
                runtime_dyn_savestate_bfs=bool(int(args.runtime_dyn_savestate_bfs or 0)),
                runtime_static_only_safe_by_offset=(
                    Path(args.runtime_static_only_safe_by_offset)
                    if args.runtime_static_only_safe_by_offset
                    else None
                ),
                logger=_default_logger,
            )
    except Exception as exc:
        print(f"[RUNTIME_QA][ERROR] {exc}", flush=True)
        return 1

    print("RUNTIME_QA_RESULT_JSON=" + json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
