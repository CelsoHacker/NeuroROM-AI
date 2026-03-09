#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera script Lua de AutoProbe para BizHawk a partir de seeds do pure_text.jsonl.
Sem scan cego: usa apenas offsets seed.
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
        inner = []
        for item in value:
            inner.append(f"{pad}  {_to_lua_table(item, indent + 2)}")
        return "{\n" + ",\n".join(inner) + f"\n{pad}" + "}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        inner = []
        for key in sorted(value.keys()):
            val = value[key]
            if str(key).isidentifier():
                kexpr = str(key)
            else:
                kexpr = f'["{_lua_escape(str(key))}"]'
            inner.append(f"{pad}  {kexpr} = {_to_lua_table(val, indent + 2)}")
        return "{\n" + ",\n".join(inner) + f"\n{pad}" + "}"
    return f'"{_lua_escape(str(value))}"'


def _sanitize_memory_domains(domains: Any) -> List[str]:
    out: List[str] = []
    for raw in list(domains or []):
        name = str(raw or "").strip()
        if not name:
            continue
        if name.lower() == "68k ram":
            continue
        if name not in out:
            out.append(name)
    return out


def render_probe_lua(payload: Dict[str, Any]) -> str:
    output_jsonl = str(payload["probe_hits_path"]).replace("\\", "/")
    seeds_lua = _to_lua_table(payload.get("seeds", []), indent=0)
    autoplay_lua = _to_lua_table(payload.get("autoplay_sequence", []), indent=0)
    memory_domains_lua = _to_lua_table(payload.get("memory_domains", []), indent=0)
    pointer_regs_lua = _to_lua_table(payload.get("pointer_registers", []), indent=0)
    meta_json = json.dumps(
        {
            "type": "meta",
            "schema": "runtime_probe_hits.v1",
            "rom_crc32": payload.get("rom_crc32"),
            "rom_size": payload.get("rom_size"),
            "platform": payload.get("platform"),
            "generator": "generate_probe_bizhawk.py",
            "seeds_total": len(payload.get("seeds", [])),
        },
        ensure_ascii=False,
    )
    sample_every = int(payload.get("sample_every_frames", 6))
    max_len = int(payload.get("max_bytes_per_capture", 192))
    max_frames = int(payload.get("max_frames", 18000))

    return f"""-- Auto-gerado por NeuroROM RuntimeQA (BizHawk AutoProbe)
-- CRC32={payload.get("rom_crc32")} PLATFORM={payload.get("platform")}

local output_file = "{_lua_escape(output_jsonl)}"
local seeds = {seeds_lua}
local autoplay = {autoplay_lua}
local memory_domains = {memory_domains_lua}
local pointer_regs = {pointer_regs_lua}
local sample_every_frames = {sample_every}
local max_capture_len = {max_len}
local max_frames = {max_frames}
local meta_line = "{_lua_escape(meta_json)}"
local RAM_DOMAIN_CANDIDATES = {{"Z80 BUS", "RAM", "Work RAM", "WRAM", "Main RAM", "System Bus"}}
local VRAM_DOMAIN_CANDIDATES = {{"VRAM", "VDP VRAM"}}

local function write_line(line)
  local f = io.open(output_file, "a")
  if not f then return end
  f:write(line .. "\\n")
  f:close()
end

local function reset_output()
  local f = io.open(output_file, "w")
  if not f then return end
  f:write(meta_line .. "\\n")
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
  for _, c in ipairs(candidates) do
    local v = get_reg(c)
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

local function log_startup(msg)
  local text = tostring(msg or "")
  if console and console.log then
    pcall(function() console.log(text) end)
    return
  end
  pcall(function() print(text) end)
end

local function try_use_domain(domain_name)
  if not memory or not memory.usememorydomain then return false end
  local ok = pcall(function() memory.usememorydomain(domain_name) end)
  return ok
end

local function get_memory_domains()
  if not memory or not memory.getmemorydomainlist then return {{}} end
  local ok, domains = pcall(function() return memory.getmemorydomainlist() end)
  if not ok or type(domains) ~= "table" then return {{}} end
  return domains
end

local function is_vram_domain(name)
  local n = tostring(name or ""):lower()
  return (n == "vram" or n == "vdp vram")
end

local AVAILABLE_DOMAINS = get_memory_domains()
local AVAILABLE_SET = {{}}
for _, dom in ipairs(AVAILABLE_DOMAINS) do
  AVAILABLE_SET[tostring(dom)] = true
end

local function domain_exists(name)
  local n = tostring(name or "")
  if n == "" then return false end
  if #AVAILABLE_DOMAINS > 0 then
    return AVAILABLE_SET[n] == true
  end
  return nil
end

local function pick_domain(candidates, extras, allow_vram)
  local function accept(name)
    local n = tostring(name or "")
    if n == "" then return nil end
    if (not allow_vram) and is_vram_domain(n) then return nil end
    local exists = domain_exists(n)
    if exists == true then
      return n
    end
    if exists == false then
      return nil
    end
    if try_use_domain(n) then
      return n
    end
    return nil
  end

  for _, cand in ipairs(candidates or {{}}) do
    local chosen = accept(cand)
    if chosen then return chosen end
  end
  for _, cand in ipairs(extras or {{}}) do
    local chosen = accept(cand)
    if chosen then return chosen end
  end
  if #AVAILABLE_DOMAINS > 0 then
    for _, dom in ipairs(AVAILABLE_DOMAINS) do
      local n = tostring(dom or "")
      if n ~= "" and (allow_vram or (not is_vram_domain(n))) then
        return n
      end
    end
  end
  return nil
end

local function build_domain_priority(primary, extras)
  local out = {{}}
  local seen = {{}}
  local function push(name)
    local n = tostring(name or "")
    if n == "" or seen[n] then return end
    seen[n] = true
    out[#out + 1] = n
  end
  push(primary)
  if type(extras) == "table" then
    for _, name in ipairs(extras) do
      push(name)
    end
  end
  return out
end

local RAM_DOMAIN = pick_domain(RAM_DOMAIN_CANDIDATES, memory_domains, false)
local VRAM_DOMAIN = pick_domain(VRAM_DOMAIN_CANDIDATES, memory_domains, true)
local READ_DOMAINS_RAM = {{}}
for _, domain in ipairs(build_domain_priority(RAM_DOMAIN, memory_domains)) do
  local n = tostring(domain or "")
  if n ~= "" and (not is_vram_domain(n)) then
    local exists = domain_exists(n)
    if exists == true or (exists == nil and try_use_domain(n)) then
      READ_DOMAINS_RAM[#READ_DOMAINS_RAM + 1] = n
    end
  end
end
if #READ_DOMAINS_RAM == 0 and #AVAILABLE_DOMAINS > 0 then
  for _, dom in ipairs(AVAILABLE_DOMAINS) do
    local n = tostring(dom or "")
    if n ~= "" and (not is_vram_domain(n)) then
      READ_DOMAINS_RAM[#READ_DOMAINS_RAM + 1] = n
      break
    end
  end
end
if (RAM_DOMAIN == nil or RAM_DOMAIN == "") and #READ_DOMAINS_RAM > 0 then
  RAM_DOMAIN = READ_DOMAINS_RAM[1]
end
local active_domain = nil

local function set_domain(name)
  local target = tostring(name or "")
  if target == "" then return false end
  if active_domain == target then return true end
  local exists = domain_exists(target)
  if exists == false then return false end
  if not try_use_domain(target) then return false end
  active_domain = target
  return true
end

local function read_seed_bytes(seed)
  local out = {{}}
  for _, domain in ipairs(READ_DOMAINS_RAM) do
    if set_domain(domain) then
      local len = tonumber(seed.raw_len) or tonumber(seed.max_len_bytes) or 0
      if len <= 0 then len = 1 end
      if len > max_capture_len then len = max_capture_len end
      for i = 0, len - 1 do
        local b = 0
        local ok = pcall(function()
          if memory.read_u8 then
            b = memory.read_u8(seed.rom_offset + i)
          elseif memory.readbyte then
            b = memory.readbyte(seed.rom_offset + i)
          end
        end)
        if not ok then break end
        out[#out + 1] = tonumber(b) or 0
      end
      if #out > 0 then
        return out
      end
    end
  end
  return out
end

local function write_hit(seed, reason)
  local frame = 0
  if emu and emu.framecount then frame = emu.framecount() end
  local bytes = read_seed_bytes(seed)
  if #bytes == 0 then return end
  local raw_hex = bytes_to_hex(bytes)
  local pc = get_pc()
  local ptr_buf = string.format("ROM:0x%X", tonumber(seed.rom_offset) or 0)
  local row = string.format(
    '{{"frame":%d,"pc":%s,"ptr_or_buf":"%s","raw_bytes_hex":"%s","raw_len":%d,"terminator":%s,"context_tag":"%s","seed_id":%s,"seed_key":"%s","seed_offset":"0x%06X","reason":"%s"}}',
    frame,
    pc and ('"' .. esc(pc) .. '"') or "null",
    esc(ptr_buf),
    raw_hex,
    #bytes,
    (seed.terminator ~= nil) and tostring(seed.terminator) or "null",
    esc(infer_context_tag(frame)),
    (seed.id ~= nil) and tostring(seed.id) or "null",
    esc(seed.key or ""),
    tonumber(seed.rom_offset) or 0,
    esc(reason or "periodic")
  )
  write_line(row)
end

local function apply_autoplay(frame)
  if not joypad then return end
  if #autoplay == 0 then return end
  local slot = ((math.floor(frame / 30)) % #autoplay) + 1
  local action = autoplay[slot]
  local btn = tostring(action.button or "")
  local state = {{}}
  if btn ~= "" then
    state[btn] = true
  end
  local ok = pcall(function() joypad.set(1, state) end)
  if not ok then
    pcall(function() joypad.set(state) end)
  end
end

local function register_exec_hooks()
  if not event then return end
  if not event.onmemoryexecute then return end
  local domain = RAM_DOMAIN
  if not domain or tostring(domain) == "" then return end
  for _, seed in ipairs(seeds) do
    pcall(function()
      event.onmemoryexecute(
        function()
          write_hit(seed, "exec_hook")
        end,
        tonumber(seed.rom_offset) or 0,
        domain,
        "NR_QA_PROBE_" .. tostring(seed.key or "seed")
      )
    end)
  end
end

local function log_domains_startup()
  if #AVAILABLE_DOMAINS > 0 then
    log_startup("[NR_QA][PROBE] Dominios disponiveis: " .. table.concat(AVAILABLE_DOMAINS, ", "))
  else
    log_startup("[NR_QA][PROBE] Dominios disponiveis: <indisponivel>")
  end
  log_startup(string.format("[NR_QA][PROBE] RAM_DOMAIN=%s | VRAM_DOMAIN=%s", tostring(RAM_DOMAIN), tostring(VRAM_DOMAIN)))
  log_startup("[NR_QA][PROBE] READ_DOMAINS_RAM=" .. table.concat(READ_DOMAINS_RAM, ", "))
end

reset_output()
log_domains_startup()
register_exec_hooks()

while true do
  local frame = 0
  if emu and emu.framecount then frame = emu.framecount() end
  if frame >= max_frames then
    if client and client.exit then
      pcall(function() client.exit() end)
    end
    return
  end
  apply_autoplay(frame)
  if (frame % sample_every_frames) == 0 then
    for _, seed in ipairs(seeds) do
      write_hit(seed, "periodic")
    end
  end
  emu.frameadvance()
end
"""


def build_probe_payload(
    pure_jsonl: Path,
    platform_hint: Optional[str] = None,
    seeds_limit: int = 256,
    sample_every_frames: int = 6,
    max_frames: int = 18000,
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

    payload = {
        "schema": "runtime_probe_config.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": str(platform),
        "pure_jsonl": str(pure_jsonl),
        "out_dir": str(out_dir),
        "sample_every_frames": int(max(1, sample_every_frames)),
        "max_frames": int(max(120, max_frames)),
        "max_bytes_per_capture": int(profile.get("max_bytes_per_capture", 192)),
        "default_terminators": profile.get("default_terminators", [0]),
        "memory_domains": _sanitize_memory_domains(profile.get("memory_domains", ["System Bus"]))
        or ["System Bus"],
        "pointer_registers": profile.get("pointer_registers", []),
        "autoplay_sequence": profile.get("autoplay_sequence", []),
        "seeds": seeds,
        "probe_script_path": str(out_dir / f"{crc}_probe_autoprobe.lua"),
        "probe_hits_path": str(out_dir / f"{crc}_probe_hits.jsonl"),
    }
    return payload


def write_probe_artifacts(payload: Dict[str, Any]) -> Dict[str, str]:
    out_dir = Path(payload["out_dir"])
    script_path = Path(payload["probe_script_path"])
    config_path = out_dir / f"{payload['rom_crc32']}_probe_config.json"
    lua_code = render_probe_lua(payload)
    script_path.write_text(lua_code, encoding="utf-8")
    write_json(config_path, payload)
    return {
        "probe_script_path": str(script_path),
        "probe_config_path": str(config_path),
        "probe_hits_path": str(payload["probe_hits_path"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera script BizHawk AutoProbe por seeds do pure_text.jsonl.")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--platform", default=None, help="Forca plataforma (opcional)")
    ap.add_argument("--seeds", type=int, default=256, help="Quantidade maxima de seeds")
    ap.add_argument("--sample-every-frames", type=int, default=6, help="Periodicidade de coleta")
    ap.add_argument("--max-frames", type=int, default=18000, help="Frames maximos antes de auto-exit")
    ap.add_argument("--out-base", default=None, help="Base de saida (default: .../out/<CRC>/runtime)")
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl nao encontrado: {pure_jsonl}")

    payload = build_probe_payload(
        pure_jsonl=pure_jsonl,
        platform_hint=args.platform,
        seeds_limit=max(1, int(args.seeds)),
        sample_every_frames=max(1, int(args.sample_every_frames)),
        max_frames=max(120, int(args.max_frames)),
        out_base=Path(args.out_base).expanduser().resolve() if args.out_base else None,
    )
    artifacts = write_probe_artifacts(payload)
    print(json.dumps(artifacts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
