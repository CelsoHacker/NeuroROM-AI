#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera script Lua de Runtime Trace + Autoplay para BizHawk usando runtime_hook_profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .common import (
        default_runtime_dir,
        extract_seed_items,
        infer_platform_from_path,
        infer_crc_size,
        load_json,
        load_platform_profile,
        load_pure_text,
        parse_int,
        write_json,
    )
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        default_runtime_dir,
        extract_seed_items,
        infer_platform_from_path,
        infer_crc_size,
        load_json,
        load_platform_profile,
        load_pure_text,
        parse_int,
        write_json,
    )


def _lua_escape(value: str) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _to_lua_table(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{_lua_escape(value)}"'
    if isinstance(value, list):
        if not value:
            return "{}"
        inner = [f"{pad}  {_to_lua_table(v, indent + 2)}" for v in value]
        return "{\n" + ",\n".join(inner) + f"\n{pad}" + "}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        inner: List[str] = []
        for key in sorted(value.keys()):
            if str(key).isidentifier():
                k = str(key)
            else:
                k = f'["{_lua_escape(str(key))}"]'
            inner.append(f"{pad}  {k} = {_to_lua_table(value[key], indent + 2)}")
        return "{\n" + ",\n".join(inner) + f"\n{pad}" + "}"
    return f'"{_lua_escape(str(value))}"'


def _build_watch_pcs(profile: Dict[str, Any], max_watch: int) -> List[str]:
    out: List[str] = []
    for row in profile.get("top_pcs", []) or []:
        if not isinstance(row, dict):
            continue
        pc = str(row.get("pc", "") or "").strip()
        if not pc:
            continue
        if pc not in out:
            out.append(pc)
        if len(out) >= max_watch:
            break
    return out


def _build_pointer_registers(profile: Dict[str, Any], platform_profile: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    recommended = (profile.get("recommended_hook", {}) or {}).get("ptr_register")
    if isinstance(recommended, str) and recommended.strip():
        out.append(recommended.strip())
    for row in profile.get("pointer_candidates", []) or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "") or "").strip()
        if name and name not in out:
            out.append(name)
    for name in platform_profile.get("pointer_registers", []) or []:
        n = str(name).strip()
        if n and n not in out:
            out.append(n)
    return out[:16]


def render_trace_lua(payload: Dict[str, Any]) -> str:
    output_jsonl = str(payload["runtime_trace_path"]).replace("\\", "/")
    watch_pcs_lua = _to_lua_table(payload.get("watch_pcs", []), indent=0)
    ptr_regs_lua = _to_lua_table(payload.get("pointer_registers", []), indent=0)
    terms_lua = _to_lua_table(payload.get("default_terminators", [0]), indent=0)
    domains_lua = _to_lua_table(payload.get("memory_domains", []), indent=0)
    autoplay_lua = _to_lua_table(payload.get("autoplay_sequence", []), indent=0)
    seeds_lua = _to_lua_table(payload.get("seed_fallback", []), indent=0)
    sample_every = int(payload.get("sample_every_frames", 8))
    max_len = int(payload.get("max_bytes_per_capture", 224))
    max_frames = int(payload.get("max_frames", 24000))
    meta_json = json.dumps(
        {
            "type": "meta",
            "schema": "runtime_trace.v1",
            "rom_crc32": payload.get("rom_crc32"),
            "rom_size": payload.get("rom_size"),
            "platform": payload.get("platform"),
            "generator": "generate_trace_autoplay_bizhawk.py",
            "watch_pcs_total": len(payload.get("watch_pcs", [])),
        },
        ensure_ascii=False,
    )

    return f"""-- Auto-gerado por NeuroROM RuntimeQA (BizHawk Runtime Trace + Autoplay)
-- CRC32={payload.get("rom_crc32")} PLATFORM={payload.get("platform")}

local output_file = "{_lua_escape(output_jsonl)}"
local watch_pcs = {watch_pcs_lua}
local pointer_regs = {ptr_regs_lua}
local terminators = {terms_lua}
local memory_domains = {domains_lua}
local autoplay = {autoplay_lua}
local seed_fallback = {seeds_lua}
local sample_every_frames = {sample_every}
local max_capture_len = {max_len}
local max_frames = {max_frames}
local meta_line = "{_lua_escape(meta_json)}"

local function reset_output()
  local f = io.open(output_file, "w")
  if not f then return end
  f:write(meta_line .. "\\n")
  f:close()
end

local function write_line(line)
  local f = io.open(output_file, "a")
  if not f then return end
  f:write(line .. "\\n")
  f:close()
end

local function esc(s)
  if s == nil then return "" end
  s = tostring(s)
  s = s:gsub("\\\\", "\\\\\\\\")
  s = s:gsub('"', '\\\\"')
  s = s:gsub("\\n", "\\\\n")
  s = s:gsub("\\r", "\\\\r")
  s = s:gsub("\\t", "\\\\t")
  return s
end

local function bytes_to_hex(bytes)
  local t = {{}}
  for i = 1, #bytes do
    t[#t + 1] = string.format("%02X", bytes[i])
  end
  return table.concat(t)
end

local function get_reg(name)
  if not emu or not emu.getregister then return nil end
  local ok, v = pcall(function() return emu.getregister(name) end)
  if ok then return v end
  return nil
end

local function get_pc()
  local candidates = {{"PC", "pc", "R15"}}
  for _, name in ipairs(candidates) do
    local v = get_reg(name)
    if v ~= nil then
      if type(v) == "number" then
        return string.format("0x%X", v)
      end
      return tostring(v)
    end
  end
  return nil
end

local function infer_context_tag(frame)
  if frame < 1800 then return "intro" end
  if frame < 3600 then return "menu" end
  if frame < 9000 then return "dialog" end
  return "gameplay"
end

local function apply_autoplay(frame)
  if not joypad then return end
  if #autoplay == 0 then return end

  local function normalize_button_name(btn)
    local txt = tostring(btn or "")
    txt = txt:gsub("^%s+", ""):gsub("%s+$", "")
    txt = txt:gsub("[%s_%-]+", "")
    txt = txt:upper()
    return txt
  end

  local button_aliases = {{
    UP = {{"Up", "UP", "P1 Up", "P1 UP"}},
    DOWN = {{"Down", "DOWN", "P1 Down", "P1 DOWN"}},
    LEFT = {{"Left", "LEFT", "P1 Left", "P1 LEFT"}},
    RIGHT = {{"Right", "RIGHT", "P1 Right", "P1 RIGHT"}},
    START = {{"Start", "START", "P1 Start", "P1 START", "Run", "P1 Run"}},
    SELECT = {{"Select", "SELECT", "P1 Select", "P1 SELECT", "Mode", "P1 Mode"}},
    A = {{"A", "P1 A", "B1", "P1 B1", "Button 1", "P1 Button 1"}},
    B = {{"B", "P1 B", "B2", "P1 B2", "Button 2", "P1 Button 2"}},
    C = {{"C", "P1 C", "B3", "P1 B3", "Button 3", "P1 Button 3"}},
    X = {{"X", "P1 X", "B4", "P1 B4"}},
    Y = {{"Y", "P1 Y", "B5", "P1 B5"}},
    Z = {{"Z", "P1 Z", "B6", "P1 B6"}},
    L = {{"L", "P1 L", "L1", "P1 L1"}},
    R = {{"R", "P1 R", "R1", "P1 R1"}}
  }}

  local function action_frames(action, default_frames)
    local d = tonumber(default_frames) or 30
    local f = tonumber((action or {{}}).frames)
    if f == nil then
      f = tonumber((action or {{}}).duration)
    end
    if f == nil then
      f = d
    end
    return math.max(1, math.floor(f))
  end

  local function pick_action(seq, tick, default_frames)
    if not seq or #seq == 0 then
      return nil
    end
    local cycle = 0
    for i = 1, #seq do
      cycle = cycle + action_frames(seq[i], default_frames)
    end
    if cycle <= 0 then
      return seq[1]
    end
    local pos = (tonumber(tick) or 0) % cycle
    local acc = 0
    for i = 1, #seq do
      acc = acc + action_frames(seq[i], default_frames)
      if pos < acc then
        return seq[i]
      end
    end
    return seq[#seq]
  end

  local action = pick_action(autoplay, frame, 30)
  if action == nil then
    return
  end
  local btn = tostring(action.button or "")
  if btn == "" then
    return
  end
  local aliases = button_aliases[normalize_button_name(btn)]
  if aliases == nil or #aliases == 0 then
    aliases = {{btn}}
  end
  local state = {{}}
  for _, name in ipairs(aliases) do
    state[tostring(name)] = true
  end
  local ok = pcall(function() joypad.set(1, state) end)
  if not ok then
    pcall(function() joypad.set(state) end)
  end
end

local function use_domain(domain_name)
  if not memory or not memory.usememorydomain then return false end
  local ok = pcall(function() memory.usememorydomain(domain_name) end)
  return ok
end

local function read_until_terminator(ptr)
  local out = {{}}
  local used_term = nil
  local domains = memory_domains
  if #domains == 0 then domains = {{"System Bus"}} end
  for _, domain in ipairs(domains) do
    if use_domain(domain) then
      for i = 0, max_capture_len - 1 do
        local b = nil
        local ok = pcall(function()
          if memory.read_u8 then
            b = memory.read_u8(ptr + i)
          elseif memory.readbyte then
            b = memory.readbyte(ptr + i)
          end
        end)
        if not ok or b == nil then break end
        b = tonumber(b) or 0
        out[#out + 1] = b
        for _, t in ipairs(terminators) do
          if b == tonumber(t) then
            used_term = tonumber(t)
            return out, used_term
          end
        end
      end
      if #out > 0 then return out, used_term end
    end
  end
  return out, used_term
end

local function write_trace_row(ptr_value, ptr_reg_name, reason)
  local frame = 0
  if emu and emu.framecount then frame = emu.framecount() end
  local bytes, used_term = read_until_terminator(ptr_value)
  if #bytes == 0 then return end
  local raw_hex = bytes_to_hex(bytes)
  local pc = get_pc()
  local ptr_or_buf = string.format("REG:%s=0x%X", tostring(ptr_reg_name or "UNK"), tonumber(ptr_value) or 0)
  local row = string.format(
    '{{"frame":%d,"pc":%s,"ptr_or_buf":"%s","raw_bytes_hex":"%s","raw_len":%d,"terminator":%s,"context_tag":"%s","ptr_register":"%s","reason":"%s"}}',
    frame,
    pc and ('"' .. esc(pc) .. '"') or "null",
    esc(ptr_or_buf),
    raw_hex,
    #bytes,
    used_term and tostring(used_term) or "null",
    esc(infer_context_tag(frame)),
    esc(ptr_reg_name or ""),
    esc(reason or "")
  )
  write_line(row)
end

local function capture_from_registers(reason)
  for _, reg in ipairs(pointer_regs) do
    local v = get_reg(reg)
    if v ~= nil and type(v) == "number" and v >= 0 then
      write_trace_row(v, reg, reason)
    end
  end
end

local function capture_from_seed(seed, reason)
  local ptr = tonumber(seed.rom_offset) or 0
  if ptr < 0 then return end
  write_trace_row(ptr, "SEED", reason)
end

local function pc_to_number(pc_text)
  if not pc_text then return nil end
  local s = tostring(pc_text)
  local hex = s:match("^0x([0-9A-Fa-f]+)$")
  if hex then
    return tonumber(hex, 16)
  end
  return tonumber(s)
end

local function register_pc_hooks()
  if not event or not event.onmemoryexecute then return end
  local domain = memory_domains[1] or "System Bus"
  for _, pc_text in ipairs(watch_pcs) do
    local pc_num = pc_to_number(pc_text)
    if pc_num then
      pcall(function()
        event.onmemoryexecute(
          function()
            capture_from_registers("pc_hook")
          end,
          pc_num,
          domain,
          "NR_QA_TRACE_" .. tostring(pc_text)
        )
      end)
    end
  end
end

reset_output()
register_pc_hooks()

while true do
  local frame = emu and emu.framecount and emu.framecount() or 0
  if frame >= max_frames then
    if client and client.exit then
      pcall(function() client.exit() end)
    end
    return
  end
  apply_autoplay(frame)
  if (frame % sample_every_frames) == 0 then
    capture_from_registers("periodic_regs")
    for _, seed in ipairs(seed_fallback) do
      capture_from_seed(seed, "periodic_seed")
    end
  end
  emu.frameadvance()
end
"""


def build_trace_payload(
    pure_jsonl: Path,
    hook_profile_path: Path,
    platform_hint: Optional[str] = None,
    max_watch_pcs: int = 24,
    seeds_fallback: int = 64,
    sample_every_frames: int = 8,
    max_frames: int = 24000,
    trace_suffix: str = "",
    out_base: Optional[Path] = None,
) -> Dict[str, Any]:
    hook_profile = load_json(hook_profile_path, {})
    if not hook_profile:
        raise ValueError(f"runtime_hook_profile invalido: {hook_profile_path}")

    meta, rows = load_pure_text(pure_jsonl)
    platform = str(
        platform_hint
        or hook_profile.get("platform")
        or infer_platform_from_path(str(pure_jsonl), fallback="master_system")
    ).lower()
    platform_profile = load_platform_profile(platform)
    crc, rom_size = infer_crc_size(meta, pure_jsonl)
    if hook_profile.get("rom_crc32"):
        crc = str(hook_profile.get("rom_crc32")).upper()
    size_from_hook = parse_int(hook_profile.get("rom_size"), default=None)
    if size_from_hook is not None and size_from_hook > 0:
        rom_size = int(size_from_hook)

    out_dir = default_runtime_dir(pure_jsonl, crc32=crc, out_base=out_base)
    out_dir.mkdir(parents=True, exist_ok=True)
    watch_pcs = _build_watch_pcs(hook_profile, max_watch=max_watch_pcs)
    ptr_regs = _build_pointer_registers(hook_profile, platform_profile)
    seed_fb = extract_seed_items(rows, limit=seeds_fallback, only_safe=True)
    suffix = str(trace_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix

    payload = {
        "schema": "runtime_trace_config.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "pure_jsonl": str(pure_jsonl),
        "hook_profile_path": str(hook_profile_path),
        "out_dir": str(out_dir),
        "watch_pcs": watch_pcs,
        "pointer_registers": ptr_regs,
        "memory_domains": platform_profile.get("memory_domains", ["System Bus"]),
        "default_terminators": platform_profile.get("default_terminators", [0]),
        "max_bytes_per_capture": int(platform_profile.get("max_bytes_per_capture", 224)),
        "autoplay_sequence": platform_profile.get("autoplay_sequence", []),
        "sample_every_frames": int(max(1, sample_every_frames)),
        "max_frames": int(max(120, max_frames)),
        "seed_fallback": seed_fb,
        "runtime_trace_script_path": str(out_dir / f"{crc}_runtime_trace_autoplay{suffix}.lua"),
        "runtime_trace_path": str(out_dir / f"{crc}_runtime_trace{suffix}.jsonl"),
    }
    return payload


def write_trace_artifacts(payload: Dict[str, Any]) -> Dict[str, str]:
    out_dir = Path(payload["out_dir"])
    script_path = Path(payload["runtime_trace_script_path"])
    config_path = out_dir / f"{payload['rom_crc32']}_runtime_trace_config.json"
    script_path.write_text(render_trace_lua(payload), encoding="utf-8")
    write_json(config_path, payload)
    return {
        "runtime_trace_script_path": str(script_path),
        "runtime_trace_config_path": str(config_path),
        "runtime_trace_path": str(payload["runtime_trace_path"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera script BizHawk Runtime Trace + Autoplay.")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--hook-profile", required=True, help="Arquivo {CRC32}_runtime_hook_profile.json")
    ap.add_argument("--platform", default=None, help="Forca plataforma")
    ap.add_argument("--max-watch-pcs", type=int, default=24, help="Maximo de PCs monitorados")
    ap.add_argument("--seeds-fallback", type=int, default=64, help="Seeds fallback no trace")
    ap.add_argument("--sample-every-frames", type=int, default=8, help="Periodicidade de coleta")
    ap.add_argument("--max-frames", type=int, default=24000, help="Frames maximos antes de auto-exit")
    ap.add_argument("--trace-suffix", default="", help="Sufixo do arquivo de trace (ex.: scenario)")
    ap.add_argument("--out-base", default=None, help="Base de saida (default: .../out/<CRC>/runtime)")
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl nao encontrado: {pure_jsonl}")
    hook_profile = Path(args.hook_profile).expanduser().resolve()
    if not hook_profile.exists():
        raise SystemExit(f"[ERRO] hook-profile nao encontrado: {hook_profile}")

    payload = build_trace_payload(
        pure_jsonl=pure_jsonl,
        hook_profile_path=hook_profile,
        platform_hint=args.platform,
        max_watch_pcs=max(1, int(args.max_watch_pcs)),
        seeds_fallback=max(1, int(args.seeds_fallback)),
        sample_every_frames=max(1, int(args.sample_every_frames)),
        max_frames=max(120, int(args.max_frames)),
        trace_suffix=str(args.trace_suffix or ""),
        out_base=Path(args.out_base).expanduser().resolve() if args.out_base else None,
    )
    artifacts = write_trace_artifacts(payload)
    print(json.dumps(artifacts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
