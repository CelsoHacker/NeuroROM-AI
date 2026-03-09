#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera script Lua para BizHawk/EmuHawk capturar texto dinâmico por tilemap/VRAM.

Suposições mínimas:
- O domínio de memória "VRAM" está disponível no core do console.
- A NameTable pode ser estimada por bases candidatas por plataforma.
- O fontmap é opcional; sem ele usa fallback ASCII quando possível.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .common import (
        default_runtime_dir,
        infer_crc_size,
        infer_platform_from_path,
        load_platform_profile,
        load_pure_text,
        write_json,
    )
    from .dyn_text_pipeline import load_fontmap
except ImportError:  # pragma: no cover
    from common import (  # type: ignore
        default_runtime_dir,
        infer_crc_size,
        infer_platform_from_path,
        load_platform_profile,
        load_pure_text,
        write_json,
    )
    from dyn_text_pipeline import load_fontmap  # type: ignore


PLATFORM_TILEMAP_HINTS: Dict[str, Dict[str, Any]] = {
    "master_system": {
        "nametable_bases": [0x3800, 0x3000, 0x3C00, 0x2000],
        "pattern_bases": [0x0000, 0x0800, 0x1000, 0x1800, 0x2000, 0x2800, 0x3000, 0x3800],
        "tile_cols": 32,
        "tile_rows": 28,
        "entry_bytes": 2,
        "tile_pattern_bytes": 32,
        "memory_domains": ["VRAM", "System Bus", "Main RAM"],
    },
    "megadrive": {
        "nametable_bases": [0xC000, 0xE000, 0xA000, 0x8000],
        "pattern_bases": [0x0000, 0x2000, 0x4000, 0x6000],
        "tile_cols": 40,
        "tile_rows": 28,
        "entry_bytes": 2,
        "tile_pattern_bytes": 32,
        "memory_domains": ["VRAM", "System Bus", "Main RAM", "Work RAM", "WRAM", "RAM"],
    },
    "snes": {
        "nametable_bases": [0x0000, 0x0800, 0x1000, 0x1800],
        "pattern_bases": [0x0000, 0x1000, 0x2000, 0x3000],
        "tile_cols": 32,
        "tile_rows": 32,
        "entry_bytes": 2,
        "tile_pattern_bytes": 32,
        "memory_domains": ["VRAM", "WRAM", "System Bus"],
    },
    "nes": {
        "nametable_bases": [0x2000, 0x2400, 0x2800, 0x2C00],
        "pattern_bases": [0x0000, 0x1000],
        "tile_cols": 32,
        "tile_rows": 30,
        "entry_bytes": 1,
        "tile_pattern_bytes": 16,
        "memory_domains": ["PPU Bus", "VRAM", "System Bus", "RAM"],
    },
    "gba": {
        "nametable_bases": [0x0000, 0x0800, 0x1000, 0x1800],
        "pattern_bases": [0x0000, 0x2000, 0x4000, 0x6000],
        "tile_cols": 32,
        "tile_rows": 32,
        "entry_bytes": 2,
        "tile_pattern_bytes": 32,
        "memory_domains": ["VRAM", "System Bus", "IWRAM"],
    },
    "n64": {
        "nametable_bases": [0x0000],
        "pattern_bases": [0x0000],
        "tile_cols": 40,
        "tile_rows": 30,
        "entry_bytes": 1,
        "tile_pattern_bytes": 32,
        "memory_domains": ["RDRAM", "System Bus"],
    },
    "ps1": {
        "nametable_bases": [0x0000],
        "pattern_bases": [0x0000],
        "tile_cols": 40,
        "tile_rows": 30,
        "entry_bytes": 1,
        "tile_pattern_bytes": 32,
        "memory_domains": ["Main RAM", "System Bus", "VRAM"],
    },
}


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
        for key in sorted(value.keys(), key=lambda k: str(k)):
            if isinstance(key, int):
                k = f"[{int(key)}]"
            elif str(key).isidentifier():
                k = str(key)
            else:
                k = f'["{_lua_escape(str(key))}"]'
            inner.append(f"{pad}  {k} = {_to_lua_table(value[key], indent + 2)}")
        return "{\n" + ",\n".join(inner) + f"\n{pad}" + "}"
    return f'"{_lua_escape(str(value))}"'


def _fallback_ascii_tile_fontmap() -> Dict[int, str]:
    out: Dict[int, str] = {}
    for i in range(32, 127):
        out[i] = chr(i)
    out[0] = " "
    return out


def _default_input_scripts(profile_autoplay: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    base = profile_autoplay or [{"button": "A", "frames": 18}, {"button": "START", "frames": 20}]
    return [
        {"name": "base", "sequence": list(base)},
        {
            "name": "menu_cycle",
            "sequence": [
                {"button": "START", "frames": 22},
                {"button": "DOWN", "frames": 16},
                {"button": "UP", "frames": 16},
                {"button": "A", "frames": 20},
                {"button": "B", "frames": 14},
            ],
        },
        {
            "name": "dialog_advance",
            "sequence": [
                {"button": "A", "frames": 20},
                {"button": "A", "frames": 20},
                {"button": "B", "frames": 16},
                {"button": "START", "frames": 14},
            ],
        },
        {
            "name": "walk_talk",
            "sequence": [
                {"button": "RIGHT", "frames": 22},
                {"button": "LEFT", "frames": 22},
                {"button": "UP", "frames": 20},
                {"button": "DOWN", "frames": 20},
                {"button": "A", "frames": 20},
            ],
        },
        {
            "name": "start_confirm_burst",
            "sequence": [
                {"button": "START", "frames": 30},
                {"button": "A", "frames": 18},
                {"button": "START", "frames": 24},
                {"button": "A", "frames": 18},
                {"button": "B", "frames": 14},
                {"button": "A", "frames": 18},
            ],
        },
        {
            "name": "intro_start_game",
            "sequence": [
                {"button": "", "frames": 28},
                {"button": "START", "frames": 8},
                {"button": "", "frames": 24},
                {"button": "A", "frames": 8},
                {"button": "", "frames": 20},
                {"button": "A", "frames": 8},
                {"button": "", "frames": 20},
                {"button": "START", "frames": 8},
                {"button": "", "frames": 18},
                {"button": "A", "frames": 8},
            ],
        },
        {
            "name": "name_entry_escape",
            "sequence": [
                {"button": "A", "frames": 14},
                {"button": "RIGHT", "frames": 14},
                {"button": "A", "frames": 14},
                {"button": "DOWN", "frames": 14},
                {"button": "A", "frames": 14},
                {"button": "START", "frames": 24},
                {"button": "B", "frames": 16},
                {"button": "START", "frames": 24},
            ],
        },
        {
            "name": "overworld_sweep",
            "sequence": [
                {"button": "UP", "frames": 34},
                {"button": "RIGHT", "frames": 34},
                {"button": "DOWN", "frames": 34},
                {"button": "LEFT", "frames": 34},
                {"button": "A", "frames": 18},
                {"button": "B", "frames": 18},
            ],
        },
        {
            "name": "menu_deep_cycle",
            "sequence": [
                {"button": "START", "frames": 22},
                {"button": "DOWN", "frames": 12},
                {"button": "DOWN", "frames": 12},
                {"button": "A", "frames": 18},
                {"button": "UP", "frames": 12},
                {"button": "A", "frames": 18},
                {"button": "B", "frames": 16},
            ],
        },
        {
            "name": "dialog_probe_long",
            "sequence": [
                {"button": "A", "frames": 8},
                {"button": "", "frames": 14},
                {"button": "A", "frames": 8},
                {"button": "", "frames": 14},
                {"button": "B", "frames": 8},
                {"button": "", "frames": 14},
                {"button": "START", "frames": 8},
                {"button": "", "frames": 16},
                {"button": "A", "frames": 8},
                {"button": "", "frames": 14},
            ],
        },
    ]


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


def render_dyn_capture_lua(payload: Dict[str, Any]) -> str:
    output_jsonl = str(payload["dyn_text_log_path"]).replace("\\", "/")
    terms_lua = _to_lua_table(payload.get("default_terminators", [0]), indent=0)
    domains_lua = _to_lua_table(payload.get("memory_domains", []), indent=0)
    bases_lua = _to_lua_table(payload.get("nametable_bases", []), indent=0)
    pattern_bases_lua = _to_lua_table(payload.get("pattern_bases", []), indent=0)
    hash_fontmap_lua = _to_lua_table(payload.get("glyph_hash_to_char", {}), indent=0)
    tile_fontmap_lua = _to_lua_table(payload.get("tile_to_char", {}), indent=0)
    autoplay_lua = _to_lua_table(payload.get("autoplay_sequence", []), indent=0)
    input_scripts_lua = _to_lua_table(payload.get("input_scripts", []), indent=0)
    sample_every = int(
        payload.get(
            "sample_every_n_frames",
            payload.get("sample_every_frames", 3),
        )
    )
    max_frames = int(payload.get("max_frames", 18000))
    capture_top_candidates = int(payload.get("capture_top_candidates", 2))
    cols = int(payload.get("tile_cols", 32))
    rows = int(payload.get("tile_rows", 28))
    entry_bytes = int(payload.get("entry_bytes", 2))
    tile_pattern_bytes = int(payload.get("tile_pattern_bytes", 32))
    unknown_char = str(payload.get("unknown_char", "?") or "?")[:1]
    prefer_tile_to_char = bool(payload.get("prefer_tile_to_char", False))
    explorer_enabled = bool(payload.get("input_explorer_enabled", False))
    explorer_switch_frames = int(payload.get("input_explorer_switch_frames", 600))
    savestate_bfs_enabled = bool(payload.get("savestate_bfs_enabled", False))
    savestate_branch_frames = int(payload.get("savestate_branch_frames", 900))
    savestate_slot_base = int(payload.get("savestate_slot_base", 1))
    savestate_slot_count = int(payload.get("savestate_slot_count", 6))
    savestate_seed_slots_lua = _to_lua_table(payload.get("savestate_seed_slots", []), indent=0)
    savestate_depth = int(payload.get("savestate_bfs_depth", 2))

    meta_json = json.dumps(
        {
            "type": "meta",
            "schema": "runtime_dyn_capture.v1",
            "rom_crc32": payload.get("rom_crc32"),
            "rom_size": payload.get("rom_size"),
            "platform": payload.get("platform"),
            "generator": "generate_dyn_capture_bizhawk.py",
            "fontmap_mode": "glyph_hash_fnv1a32",
            "input_explorer_enabled": explorer_enabled,
            "savestate_bfs_enabled": savestate_bfs_enabled,
        },
        ensure_ascii=False,
    )

    return f"""-- Auto-gerado por NeuroROM Runtime QA Dinâmico (BizHawk)
-- Captura NameTable/VRAM -> linhas de texto por tilemap
-- CRC32={payload.get("rom_crc32")} PLATFORM={payload.get("platform")}

local output_file = "{_lua_escape(output_jsonl)}"
local memory_domains = {domains_lua}
local nametable_bases = {bases_lua}
local pattern_bases = {pattern_bases_lua}
local default_terminators = {terms_lua}
local glyph_hash_to_char = {hash_fontmap_lua}
local tile_to_char = {tile_fontmap_lua}
local autoplay = {autoplay_lua}
local input_scripts = {input_scripts_lua}
local sample_every_n_frames = {sample_every}
local max_frames = {max_frames}
local capture_top_candidates = {capture_top_candidates}
local tile_cols = {cols}
local tile_rows = {rows}
local entry_bytes = {entry_bytes}
local tile_pattern_bytes = {tile_pattern_bytes}
local unknown_char = "{_lua_escape(unknown_char)}"
local prefer_tile_to_char = {"true" if prefer_tile_to_char else "false"}
local input_explorer_enabled = {"true" if explorer_enabled else "false"}
local input_explorer_switch_frames = {explorer_switch_frames}
local savestate_bfs_enabled = {"true" if savestate_bfs_enabled else "false"}
local savestate_branch_frames = {savestate_branch_frames}
local savestate_slot_base = {savestate_slot_base}
local savestate_slot_count = {savestate_slot_count}
local savestate_seed_slots = {savestate_seed_slots_lua}
local savestate_bfs_depth = {savestate_depth}
local meta_line = "{_lua_escape(meta_json)}"
local platform_id = "{_lua_escape(str(payload.get("platform", "") or ""))}"
local RAM_DOMAIN_CANDIDATES = {{"Z80 BUS", "RAM", "Work RAM", "WRAM", "Main RAM", "System Bus"}}
local VRAM_DOMAIN_CANDIDATES = {{"VRAM", "VDP VRAM"}}
local VRAM_SIZE = 16384

local seen = {{}}
local candidate_history = {{}}
local branch_idx = 0
local bfs_saves = 0
local seed_slot_cursor = 0
local seed_slot_seen = {{}}
local last_nametable_hash = nil
local step_error_logged = false
local sms_vdp_invalid_logged = false

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

local function trim(s)
  if not s then return "" end
  s = tostring(s)
  s = s:gsub("^%s+", "")
  s = s:gsub("%s+$", "")
  return s
end

local function keep_printable(s)
  if not s then return "" end
  s = tostring(s)
  return (s:gsub("[%z\\1-\\8\\11\\12\\14-\\31\\127]", ""))
end

local function bytes_to_hex(bytes)
  local t = {{}}
  for i = 1, #bytes do
    t[#t + 1] = string.format("%02X", bytes[i] or 0)
  end
  return table.concat(t)
end

local function simple_hash(text)
  local h = 5381
  for i = 1, #text do
    h = ((h * 33) + string.byte(text, i)) % 4294967291
  end
  if h < 0 then h = h + 4294967291 end
  return string.format("%08X", h)
end

local function u32(v)
  return ((tonumber(v) or 0) | 0) & 0xFFFFFFFF
end

local function mul_fnv_prime(v)
  local x = u32(v)
  local out =
    x
    + ((x << 1) & 0xFFFFFFFF)
    + ((x << 4) & 0xFFFFFFFF)
    + ((x << 7) & 0xFFFFFFFF)
    + ((x << 8) & 0xFFFFFFFF)
    + ((x << 24) & 0xFFFFFFFF)
  return u32(out)
end

local function fnv1a_32_hex(bytes)
  local h = 2166136261
  for i = 1, #bytes do
    local b = tonumber(bytes[i]) or 0
    h = (u32(h) ~ u32(b)) & 0xFFFFFFFF
    -- Normaliza com rshift para manter semântica unsigned explícita.
    h = ((h >> 0) & 0xFFFFFFFF)
    h = mul_fnv_prime(h)
  end
  return string.format("%08X", u32(h))
end

local function log_startup(msg)
  local text = tostring(msg or "")
  if console and console.log then
    pcall(function() console.log(text) end)
    return
  end
  pcall(function() print(text) end)
end

local function use_domain(name)
  if not memory or not memory.usememorydomain then return false end
  local ok = pcall(function() memory.usememorydomain(name) end)
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
    if use_domain(n) then
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
local active_domain = nil

local function resolve_domains(candidates, allow_vram)
  local out = {{}}
  local seen = {{}}
  local function push_if_valid(name)
    local n = tostring(name or "")
    if n == "" or seen[n] then return end
    if (not allow_vram) and is_vram_domain(n) then return end
    local exists = domain_exists(n)
    if exists == true then
      seen[n] = true
      out[#out + 1] = n
      return
    end
    if exists == false then
      return
    end
    if use_domain(n) then
      seen[n] = true
      out[#out + 1] = n
      return
    end
  end
  for _, name in ipairs(candidates or {{}}) do
    push_if_valid(name)
  end
  if #out == 0 and #AVAILABLE_DOMAINS > 0 then
    for _, dom in ipairs(AVAILABLE_DOMAINS) do
      local n = tostring(dom or "")
      if n ~= "" and (allow_vram or (not is_vram_domain(n))) then
        out[#out + 1] = n
        break
      end
    end
  end
  return out
end

local READ_DOMAINS_VRAM = resolve_domains(build_domain_priority(VRAM_DOMAIN, memory_domains), true)
local READ_DOMAINS_RAM = resolve_domains(build_domain_priority(RAM_DOMAIN, memory_domains), false)
if (RAM_DOMAIN == nil or RAM_DOMAIN == "") and #READ_DOMAINS_RAM > 0 then
  RAM_DOMAIN = READ_DOMAINS_RAM[1]
end
if (VRAM_DOMAIN == nil or VRAM_DOMAIN == "") and #READ_DOMAINS_VRAM > 0 then
  VRAM_DOMAIN = READ_DOMAINS_VRAM[1]
end

local function log_domains_startup()
  if #AVAILABLE_DOMAINS > 0 then
    log_startup("[NR_QA][DYN] Dominios disponiveis: " .. table.concat(AVAILABLE_DOMAINS, ", "))
  else
    log_startup("[NR_QA][DYN] Dominios disponiveis: <indisponivel>")
  end
  log_startup(string.format("[NR_QA][DYN] RAM_DOMAIN=%s | VRAM_DOMAIN=%s", tostring(RAM_DOMAIN), tostring(VRAM_DOMAIN)))
  log_startup("[NR_QA][DYN] READ_DOMAINS_VRAM=" .. table.concat(READ_DOMAINS_VRAM, ", "))
  log_startup("[NR_QA][DYN] READ_DOMAINS_RAM=" .. table.concat(READ_DOMAINS_RAM, ", "))
end

local function set_domain(name)
  local target = tostring(name or "")
  if target == "" then return false end
  if active_domain == target then return true end
  local exists = domain_exists(target)
  if exists == false then return false end
  if not use_domain(target) then return false end
  active_domain = target
  return true
end

local function mask_vram_addr(addr)
  return ((tonumber(addr) or 0) & 0x3FFF)
end

local function safe_read(domain, addr, len)
  local addr_num = tonumber(addr) or -1
  local len_num = tonumber(len) or 1
  if len_num < 1 then len_num = 1 end
  if addr_num < 0 then return nil end
  if is_vram_domain(domain) then
    addr_num = mask_vram_addr(addr_num)
    if (addr_num + len_num) > VRAM_SIZE then
      return nil
    end
  end
  return addr_num
end

local function read_u8_current(addr)
  local value = nil
  local ok = pcall(function()
    if memory.read_u8 then
      value = memory.read_u8(addr)
    elseif memory.readbyte then
      value = memory.readbyte(addr)
    end
  end)
  if ok and value ~= nil then
    return tonumber(value) or 0
  end
  return nil
end

local function read_vram_u8(addr)
  local safe_addr = safe_read(VRAM_DOMAIN, addr, 1)
  if safe_addr == nil then
    return nil
  end
  if not set_domain(VRAM_DOMAIN) then
    return nil
  end
  return read_u8_current(safe_addr)
end

local function read_vram_bytes(addr, len)
  local size = tonumber(len) or 0
  local out = {{}}
  if size <= 0 then
    return out
  end
  local safe_addr = safe_read(VRAM_DOMAIN, addr, size)
  if safe_addr == nil then
    return out
  end
  if not set_domain(VRAM_DOMAIN) then
    return out
  end
  for i = 0, size - 1 do
    local value = read_u8_current(safe_addr + i)
    if value == nil then
      return {{}}
    end
    out[#out + 1] = value
  end
  return out
end

local function score_line(line, unmapped_count)
  local txt = tostring(line or "")
  local len = #txt
  if len == 0 then return 0 end
  local score = len
  if txt:find("%a") then score = score + 8 end
  if txt:find(" ") then score = score + 3 end
  if txt:find("%d") then score = score + 2 end
  score = score - (tonumber(unmapped_count) or 0) * 2
  return score
end

local function read_pattern_bytes(pattern_base, tile_id)
  local start = mask_vram_addr((tonumber(pattern_base) or 0) + ((tonumber(tile_id) or 0) * tile_pattern_bytes))
  local bytes = read_vram_bytes(start, tile_pattern_bytes)
  if #bytes ~= tile_pattern_bytes then
    bytes = {{}}
    for _ = 1, tile_pattern_bytes do
      bytes[#bytes + 1] = 0
    end
  end
  return bytes
end

local function compute_nametable_hash(base_addr)
  local base = mask_vram_addr(base_addr)
  local h = 2166136261
  for row = 0, tile_rows - 1 do
    for col = 0, tile_cols - 1 do
      local p = mask_vram_addr(base + ((row * tile_cols + col) * entry_bytes))
      local low = read_vram_u8(p) or 0
      h = (u32(h) ~ u32(low)) & 0xFFFFFFFF
      h = mul_fnv_prime(h)
      if entry_bytes > 1 then
        local attr = read_vram_u8(mask_vram_addr(p + 1)) or 0
        h = (u32(h) ~ u32(attr)) & 0xFFFFFFFF
        h = mul_fnv_prime(h)
      end
    end
  end
  return string.format("%08X", u32(h))
end

local function glyph_repeat_score(glyph_hashes)
  if #glyph_hashes <= 1 then
    return 0
  end
  local freq = {{}}
  local repeated = 0
  for i = 1, #glyph_hashes do
    local h = tostring(glyph_hashes[i] or "")
    freq[h] = (freq[h] or 0) + 1
  end
  for _, cnt in pairs(freq) do
    if cnt > 1 then
      repeated = repeated + (cnt - 1)
    end
  end
  return repeated
end

local function glyph_diversity_score(glyph_hashes)
  if #glyph_hashes <= 0 then
    return 0.0
  end
  local uniq = {{}}
  local uniq_count = 0
  for i = 1, #glyph_hashes do
    local h = tostring(glyph_hashes[i] or "")
    if h ~= "" and not uniq[h] then
      uniq[h] = true
      uniq_count = uniq_count + 1
    end
  end
  return (uniq_count / math.max(1, #glyph_hashes))
end

local function decode_tile_row(base_addr, row_idx, pattern_base)
  local chars = {{}}
  local row_bytes = {{}}
  local unmapped = {{}}
  local glyph_hashes = {{}}
  local unmapped_hashes = {{}}
  local unknown_samples = {{}}
  local unknown_seen = {{}}
  for col = 0, tile_cols - 1 do
    local p = mask_vram_addr(base_addr + ((row_idx * tile_cols + col) * entry_bytes))
    local tile_low = read_vram_u8(p) or 0
    local tile_id = tile_low
    row_bytes[#row_bytes + 1] = tile_low
    if entry_bytes > 1 then
      local attr = read_vram_u8(mask_vram_addr(p + 1)) or 0
      row_bytes[#row_bytes + 1] = attr
      tile_id = (((attr & 0x01) << 8) | tile_low)
    end

    local pattern_bytes = read_pattern_bytes(pattern_base, tile_id)
    local pattern_hex = bytes_to_hex(pattern_bytes)
    local glyph_hash = fnv1a_32_hex(pattern_bytes)
    glyph_hashes[#glyph_hashes + 1] = glyph_hash

    local ch = nil
    if prefer_tile_to_char then
      ch = tile_to_char[tile_id]
      if ch == nil or ch == "" then
        ch = tile_to_char[(tile_id & 0x1FF)]
      end
      if ch == nil or ch == "" then
        ch = tile_to_char[(tile_id & 0xFF)]
      end
      if ch == nil or ch == "" then
        ch = glyph_hash_to_char[glyph_hash]
      end
    else
      ch = glyph_hash_to_char[glyph_hash]
      if ch == nil or ch == "" then
        ch = tile_to_char[tile_id]
      end
      if ch == nil or ch == "" then
        ch = tile_to_char[(tile_id & 0x1FF)]
      end
      if ch == nil or ch == "" then
        ch = tile_to_char[(tile_id & 0xFF)]
      end
    end
    if ch == nil or ch == "" then
      ch = unknown_char
      unmapped[#unmapped + 1] = tile_id
      unmapped_hashes[#unmapped_hashes + 1] = glyph_hash
      if not unknown_seen[glyph_hash] and #unknown_samples < 16 then
        unknown_samples[#unknown_samples + 1] = {{
          hash = glyph_hash,
          tile_id = tile_id,
          pattern_hex = pattern_hex,
        }}
        unknown_seen[glyph_hash] = true
      end
    end
    chars[#chars + 1] = ch
  end
  local line = trim(keep_printable(table.concat(chars)))
  return line, bytes_to_hex(row_bytes), unmapped, glyph_hashes, unmapped_hashes, unknown_samples
end

local function count_pattern(line, patt)
  local _, count = string.gsub(line or "", patt, "")
  return tonumber(count) or 0
end

local function is_line_quality_ok(line, unmapped_count, glyph_count)
  if line == nil or line == "" then
    return false
  end
  local len = #(line or "")
  if len <= 1 then
    return false
  end

  local spaces = count_pattern(line, "%s")
  local visible = math.max(1, len - spaces)
  local alpha_num = count_pattern(line, "[%a%d]")
  local digits = count_pattern(line, "%d")
  local q_count = count_pattern(line, "%?")
  local punct_like = math.max(0, visible - alpha_num)

  local freq = {{}}
  local max_repeat = 0
  for i = 1, len do
    local ch = string.sub(line, i, i)
    if ch ~= " " then
      local n = (freq[ch] or 0) + 1
      freq[ch] = n
      if n > max_repeat then
        max_repeat = n
      end
    end
  end

  local repeat_ratio = max_repeat / visible
  local q_ratio = q_count / visible
  local unmapped_ratio = 0.0
  if tonumber(glyph_count) and tonumber(glyph_count) > 0 then
    unmapped_ratio = (tonumber(unmapped_count) or 0) / tonumber(glyph_count)
  end

  -- Corta linhas de ruído visual (molduras/tile lixo) sem letras reais.
  if repeat_ratio >= 0.65 and alpha_num == 0 then
    return false
  end
  if q_ratio >= 0.55 and alpha_num <= 2 then
    return false
  end
  if alpha_num == 0 and unmapped_ratio >= 0.40 then
    return false
  end
  if alpha_num == 0 and digits <= 2 and repeat_ratio >= 0.45 then
    return false
  end
  if visible >= 8 and punct_like / visible >= 0.70 and alpha_num <= 2 then
    return false
  end
  return true
end

local function json_int_array(values)
  if not values or #values == 0 then
    return "[]"
  end
  local t = {{}}
  for i = 1, #values do
    t[#t + 1] = tostring(tonumber(values[i]) or 0)
  end
  return "[" .. table.concat(t, ",") .. "]"
end

local function json_string_array(values)
  if not values or #values == 0 then
    return "[]"
  end
  local t = {{}}
  for i = 1, #values do
    t[#t + 1] = string.format('"%s"', esc(values[i] or ""))
  end
  return "[" .. table.concat(t, ",") .. "]"
end

local function json_unknown_samples(values)
  if not values or #values == 0 then
    return "[]"
  end
  local t = {{}}
  for i = 1, #values do
    local it = values[i] or {{}}
    t[#t + 1] = string.format(
      '{{"hash":"%s","tile_id":%d,"pattern_hex":"%s"}}',
      esc(it.hash or ""),
      tonumber(it.tile_id) or 0,
      esc(it.pattern_hex or "")
    )
  end
  return "[" .. table.concat(t, ",") .. "]"
end

local function write_dyn_row(frame, scene_hash, nametable_base, pattern_base, line_idx, line, tile_row_hex, unmapped_tiles, glyph_hashes, unmapped_hashes, unknown_samples)
  if line == "" then return end
  local key = tostring(scene_hash) .. "|" .. tostring(pattern_base) .. "|" .. tostring(line)
  if seen[key] then return end
  seen[key] = true

  local glyph_count = #glyph_hashes
  local unmapped_count = #unmapped_hashes
  local unmapped_ratio = 0.0
  if glyph_count > 0 then
    unmapped_ratio = unmapped_count / glyph_count
  end
  if not is_line_quality_ok(line, unmapped_count, glyph_count) then
    return
  end

  local unmapped_json = json_int_array(unmapped_tiles)
  local glyph_hashes_json = json_string_array(glyph_hashes)
  local unmapped_hashes_json = json_string_array(unmapped_hashes)
  local unknown_samples_json = json_unknown_samples(unknown_samples)

  local row = string.format(
    '{{"type":"dyn_text","frame":%d,"scene_hash":"%s","nametable_base":"0x%X","pattern_base":"0x%X","line_idx":%d,"line":"%s","tile_row_hex":"%s","glyph_hashes":%s,"unmapped_tiles":%s,"unmapped_glyph_hashes":%s,"unknown_glyph_samples":%s,"glyph_count":%d,"unmapped_glyph_count":%d,"unmapped_ratio":%.4f,"source":"tilemap_vram"}}',
    tonumber(frame) or 0,
    esc(scene_hash or ""),
    tonumber(nametable_base) or 0,
    tonumber(pattern_base) or 0,
    tonumber(line_idx) or 0,
    esc(line or ""),
    esc(tile_row_hex or ""),
    glyph_hashes_json,
    unmapped_json,
    unmapped_hashes_json,
    unknown_samples_json,
    tonumber(glyph_count) or 0,
    tonumber(unmapped_count) or 0,
    tonumber(unmapped_ratio) or 0.0
  )
  write_line(row)
end

local sms_vdp_bases_logged = false

local function is_master_system_platform()
  local p = tostring(platform_id or ""):lower()
  return (p == "master_system" or p == "sms")
end

local function get_register_any(candidates)
  if not emu or not emu.getregister then return nil end
  for _, name in ipairs(candidates or {{}}) do
    local ok, value = pcall(function() return emu.getregister(name) end)
    if ok and value ~= nil then
      local num = tonumber(value)
      if num ~= nil then
        return num
      end
    end
  end
  return nil
end

local function decode_sms_vdp_bases()
  local reg2 = get_register_any({{
    "VDP Reg2", "VDP Reg 2", "VDP Register 2", "VDP:R2", "R2"
  }})
  local reg4 = get_register_any({{
    "VDP Reg4", "VDP Reg 4", "VDP Register 4", "VDP:R4", "R4"
  }})
  if reg2 == nil or reg4 == nil then
    return nil, nil
  end
  local name_table_base = (((reg2 & 0x0E) * 0x400) & 0x3FFF)
  local pattern_base = (((reg4 & 0x07) * 0x800) & 0x3FFF)
  if not sms_vdp_bases_logged then
    log_startup(
      string.format(
        "[NR_QA][DYN] SMS VDP base decode: R2=0x%02X R4=0x%02X -> name=0x%04X pattern=0x%04X",
        (reg2 & 0xFF),
        (reg4 & 0xFF),
        name_table_base,
        pattern_base
      )
    )
    sms_vdp_bases_logged = true
  end
  return name_table_base, pattern_base
end

local function merge_unique_bases(preferred, fallback)
  local out = {{}}
  local seen = {{}}

  local function push(v)
    local num = tonumber(v)
    if num == nil then
      return
    end
    num = mask_vram_addr(num)
    local key = string.format("%X", num)
    if seen[key] then
      return
    end
    seen[key] = true
    out[#out + 1] = num
  end

  for _, item in ipairs(preferred or {{}}) do
    push(item)
  end
  for _, item in ipairs(fallback or {{}}) do
    push(item)
  end
  return out
end

local function resolve_capture_bases()
  local local_name_bases = nametable_bases
  local local_pattern_bases = pattern_bases
  if not local_name_bases or #local_name_bases == 0 then
    local_name_bases = {{0x3800, 0x3000, 0x3C00, 0x2000}}
  end
  if not local_pattern_bases or #local_pattern_bases == 0 then
    local_pattern_bases = {{0x0000, 0x0800, 0x1000, 0x1800}}
  end
  if is_master_system_platform() then
    local decoded_name, decoded_pattern = decode_sms_vdp_bases()
    if decoded_name ~= nil and decoded_pattern ~= nil then
      local decoded_is_zero = ((decoded_name == 0) and (decoded_pattern == 0))
      if decoded_is_zero then
        if not sms_vdp_invalid_logged then
          log_startup("[NR_QA][DYN][WARN] SMS VDP decode retornou name/pattern=0x0000; mantendo fallback heurístico.")
          sms_vdp_invalid_logged = true
        end
      else
        local_name_bases = merge_unique_bases({{decoded_name}}, local_name_bases)
        local_pattern_bases = merge_unique_bases({{decoded_pattern}}, local_pattern_bases)
      end
    end
  end
  local_name_bases = merge_unique_bases({{}}, local_name_bases)
  local_pattern_bases = merge_unique_bases({{}}, local_pattern_bases)
  return local_name_bases, local_pattern_bases
end

local function capture_frame(frame)
  local candidates = {{}}
  local local_nametable_bases, local_pattern_bases = resolve_capture_bases()
  local primary_base = tonumber(local_nametable_bases[1])
  if primary_base ~= nil then
    local nametable_hash = compute_nametable_hash(primary_base)
    if nametable_hash ~= nil and nametable_hash == last_nametable_hash then
      -- Mesmo em cena estável, força varredura periódica para não perder
      -- texto que aparece em outros planos/bases.
      if (tonumber(frame) or 0) % 90 ~= 0 then
        return
      end
    end
    last_nametable_hash = nametable_hash
  end
  for _, base in ipairs(local_nametable_bases) do
    for _, pattern_base in ipairs(local_pattern_bases) do
      local lines = {{}}
      local score_sum = 0
      local repeat_score = 0
      local diversity_score = 0.0
      local alpha_lines = 0
      local unmapped_total = 0
      local scene_parts = {{}}
      local glyph_scene_parts = {{}}
      for row = 0, tile_rows - 1 do
        local line, row_hex, unmapped, glyph_hashes, unmapped_hashes, unknown_samples = decode_tile_row(base, row, pattern_base)
        scene_parts[#scene_parts + 1] = row_hex
        glyph_scene_parts[#glyph_scene_parts + 1] = table.concat(glyph_hashes, ",")
        repeat_score = repeat_score + glyph_repeat_score(glyph_hashes)
        diversity_score = diversity_score + glyph_diversity_score(glyph_hashes)
        unmapped_total = unmapped_total + #unmapped_hashes
        if line ~= "" then
          local score = score_line(line, #unmapped_hashes)
          score_sum = score_sum + score
          if line:find("%a") then
            alpha_lines = alpha_lines + 1
          end
          lines[#lines + 1] = {{
            line_idx = row,
            line = line,
            tile_row_hex = row_hex,
            unmapped = unmapped,
            glyph_hashes = glyph_hashes,
            unmapped_hashes = unmapped_hashes,
            unknown_samples = unknown_samples,
          }}
        end
      end

      local scene_hex = table.concat(scene_parts)
      local scene_glyph_sig = simple_hash(table.concat(glyph_scene_parts, "|"):sub(1, 2048))
      local cand_key = string.format("%X|%X", tonumber(base) or 0, tonumber(pattern_base) or 0)
      local prev = candidate_history[cand_key]
      local stability_bonus = 0
      local stable_hits = 1
      if prev and prev.scene_glyph_sig == scene_glyph_sig then
        stable_hits = (tonumber(prev.stable_hits) or 0) + 1
        stability_bonus = 80 + math.min(120, stable_hits * 6)
      end
      candidate_history[cand_key] = {{
        scene_glyph_sig = scene_glyph_sig,
        stable_hits = stable_hits,
      }}

      -- Penaliza repetição visual (molduras/UI) e favorece diversidade/linhas textuais.
      local total_score =
        score_sum
        - (repeat_score * 2)
        + (diversity_score * 18)
        + (alpha_lines * 40)
        - (unmapped_total * 2)
        + stability_bonus
      if #lines > 0 then
        candidates[#candidates + 1] = {{
          base = base,
          pattern_base = pattern_base,
          total_score = total_score,
          score_sum = score_sum,
          lines = lines,
          scene_hex = scene_hex,
          scene_glyph_sig = scene_glyph_sig,
        }}
      end
    end
  end

  if #candidates == 0 then return end
  table.sort(candidates, function(a, b)
    return (tonumber(a.total_score) or 0) > (tonumber(b.total_score) or 0)
  end)

  local best_score = tonumber(candidates[1].total_score) or 0
  local max_keep = math.max(1, tonumber(capture_top_candidates) or 1)
  local emitted = 0

  for idx, cand in ipairs(candidates) do
    if idx > max_keep then
      break
    end
    if idx > 1 and best_score > 0 then
      local rel = (tonumber(cand.total_score) or 0) / best_score
      if rel < 0.95 then
        break
      end
    end
    local scene_hash = simple_hash((cand.scene_hex .. "|" .. tostring(cand.scene_glyph_sig or "")):sub(1, 1024))
    for _, it in ipairs(cand.lines) do
      write_dyn_row(
        frame,
        scene_hash,
        cand.base,
        cand.pattern_base,
        it.line_idx,
        it.line,
        it.tile_row_hex,
        it.unmapped,
        it.glyph_hashes,
        it.unmapped_hashes,
        it.unknown_samples
      )
    end
    emitted = emitted + 1
  end

  if emitted == 0 then
    local cand = candidates[1]
    local scene_hash = simple_hash((cand.scene_hex .. "|" .. tostring(cand.scene_glyph_sig or "")):sub(1, 1024))
    for _, it in ipairs(cand.lines) do
      write_dyn_row(
        frame,
        scene_hash,
        cand.base,
        cand.pattern_base,
        it.line_idx,
        it.line,
        it.tile_row_hex,
        it.unmapped,
        it.glyph_hashes,
        it.unmapped_hashes,
        it.unknown_samples
      )
    end
  end
end

local function apply_input_action(action)
  if not joypad or not action then return end

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

  local btn = tostring(action.button or "")
  if btn == "" then return end
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

local function action_frames(action, default_frames)
  local d = tonumber(default_frames) or 24
  local f = tonumber((action or {{}}).frames)
  if f == nil then
    f = tonumber((action or {{}}).duration)
  end
  if f == nil then
    f = d
  end
  return math.max(1, math.floor(f))
end

local function pick_sequence_action(seq, tick, default_frames)
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

local function run_input_script(frame)
  if not input_explorer_enabled then
    return
  end
  if #input_scripts == 0 then
    -- Fallback de explorer.
    if #autoplay == 0 then return end
    local action = pick_sequence_action(autoplay, frame, 24)
    if action then
      apply_input_action(action)
    end
    return
  end

  local script_idx = 1
  script_idx = ((math.floor(frame / input_explorer_switch_frames)) % #input_scripts) + 1
  local script = input_scripts[script_idx]
  local seq = script and script.sequence or autoplay
  if not seq or #seq == 0 then return end
  local script_tick = frame
  if input_explorer_switch_frames > 0 then
    script_tick = frame % input_explorer_switch_frames
  end
  local action = pick_sequence_action(seq, script_tick, 18)
  if action then
    apply_input_action(action)
  end
end

local function save_slot(slot)
  if not savestate then return false end
  if savestate.saveslot then
    local ok = pcall(function() savestate.saveslot(slot) end)
    return ok
  end
  if savestate.create and savestate.save then
    local ok, obj = pcall(function() return savestate.create(slot) end)
    if ok and obj then
      local ok2 = pcall(function() savestate.save(obj) end)
      return ok2
    end
  end
  return false
end

local function load_slot(slot)
  if not savestate then return false end
  if savestate.loadslot then
    local ok = pcall(function() savestate.loadslot(slot) end)
    return ok
  end
  if savestate.create and savestate.load then
    local ok, obj = pcall(function() return savestate.create(slot) end)
    if ok and obj then
      local ok2 = pcall(function() savestate.load(obj) end)
      return ok2
    end
  end
  return false
end

local function load_next_seed_slot()
  if not savestate_seed_slots or #savestate_seed_slots == 0 then
    return false
  end
  local tries = 0
  while tries < #savestate_seed_slots do
    local idx = ((seed_slot_cursor + tries) % #savestate_seed_slots) + 1
    local slot = tonumber(savestate_seed_slots[idx])
    if slot ~= nil and slot >= 0 then
      local ok = load_slot(slot)
      if ok then
        seed_slot_cursor = idx
        local key = tostring(slot)
        if not seed_slot_seen[key] then
          log_startup(string.format("[NR_QA][DYN] seed savestate carregado: slot=%d", slot))
          seed_slot_seen[key] = true
        end
        return true
      end
    end
    tries = tries + 1
  end
  return false
end

local function maybe_bfs_step(frame)
  if not savestate_bfs_enabled then return end
  if frame == 30 then
    load_next_seed_slot()
  end
  if frame == 120 then
    save_slot(savestate_slot_base)
  end
  if frame > 0 and (frame % savestate_branch_frames) == 0 then
    local loaded_seed = load_next_seed_slot()
    if not loaded_seed then
      branch_idx = branch_idx + 1
      local target = savestate_slot_base + (branch_idx % math.max(1, savestate_slot_count))
      load_slot(target)
    end
  end
  if frame > 0 and (frame % math.max(120, math.floor(savestate_branch_frames / 2))) == 0 then
    if bfs_saves < (savestate_slot_count * math.max(1, savestate_bfs_depth)) then
      local slot = savestate_slot_base + (bfs_saves % math.max(1, savestate_slot_count))
      save_slot(slot)
      bfs_saves = bfs_saves + 1
    end
  end
end

local function request_exit()
  if client and client.exit then
    pcall(function() client.exit() end)
  end
end

local function capture_main()
  reset_output()
  log_domains_startup()
  local frame_origin = emu and emu.framecount and emu.framecount() or 0
  log_startup(string.format("[NR_QA][DYN] frame_origin=%d max_frames=%d", frame_origin, max_frames))
  -- Usa contador lógico monotônico para não quebrar quando o BFS carrega savestate.
  local logical_frame = 0

  while logical_frame < max_frames do
    local frame_now = emu and emu.framecount and emu.framecount() or 0

    local step_ok, step_err = xpcall(function()
      run_input_script(logical_frame)
      maybe_bfs_step(logical_frame)
      if (logical_frame % sample_every_n_frames) == 0 then
        capture_frame(logical_frame)
      end
    end, function(e)
      return tostring(e)
    end)
    if not step_ok and not step_error_logged then
      log_startup("[NR_QA][DYN][WARN] step error (logging once): " .. tostring(step_err))
      step_error_logged = true
    end
    emu.frameadvance()
    logical_frame = logical_frame + 1
  end
end

local ok, err = xpcall(capture_main, function(e)
  return tostring(e)
end)
if not ok then
  log_startup("[NR_QA][DYN][ERROR] " .. tostring(err))
end
request_exit()
return
"""


def build_dyn_capture_payload(
    *,
    pure_jsonl: Path,
    platform_hint: Optional[str] = None,
    fontmap_json: Optional[Path] = None,
    max_frames: int = 18000,
    sample_every_frames: int = 3,
    input_explorer_enabled: bool = False,
    input_explorer_switch_frames: int = 600,
    savestate_bfs_enabled: bool = False,
    savestate_bfs_depth: int = 2,
    savestate_branch_frames: int = 900,
    savestate_slot_base: int = 1,
    savestate_slot_count: int = 6,
    savestate_seed_slots: Optional[List[int]] = None,
    trace_suffix: str = "",
    out_base: Optional[Path] = None,
) -> Dict[str, Any]:
    meta, _rows = load_pure_text(pure_jsonl)
    platform = str(
        platform_hint or infer_platform_from_path(str(pure_jsonl), fallback="master_system")
    ).lower()
    profile = load_platform_profile(platform)
    hints = dict(PLATFORM_TILEMAP_HINTS.get(platform, PLATFORM_TILEMAP_HINTS["master_system"]))
    crc, rom_size = infer_crc_size(meta, pure_jsonl)
    out_dir = default_runtime_dir(pure_jsonl, crc32=crc, out_base=out_base)

    fontmap_bundle = load_fontmap(fontmap_json)
    hash_fontmap = dict(fontmap_bundle.get("glyph_hash_to_char", {}))
    tile_fontmap = dict(fontmap_bundle.get("tile_to_char", {}))
    # Fontmap auto gerado por .tbl é ótimo no tile_id->char, mas hash legado pode ficar ruidoso.
    # Para evitar decodificação embaralhada, priorizamos modo estável baseado em tile nesses arquivos.
    if fontmap_json and "auto_from_tbl" in str(fontmap_json.name).lower() and tile_fontmap:
        hash_fontmap = {}
    if not hash_fontmap and not tile_fontmap:
        tile_fontmap = _fallback_ascii_tile_fontmap()

    prefer_tile_to_char = bool(
        platform in {"master_system", "sms", "nes", "snes", "megadrive", "genesis", "gba"}
        and len(tile_fontmap) > 0
    )

    suffix = str(trace_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix

    domains = _sanitize_memory_domains(profile.get("memory_domains", []) or [])
    if not domains:
        domains = _sanitize_memory_domains(hints.get("memory_domains", []) or [])
    if not domains:
        domains = ["System Bus", "VRAM"]

    seed_slots: List[int] = []
    if savestate_seed_slots:
        for raw in list(savestate_seed_slots):
            try:
                slot_num = int(raw)
            except Exception:
                continue
            if slot_num < 0:
                continue
            if slot_num not in seed_slots:
                seed_slots.append(slot_num)

    payload = {
        "schema": "runtime_dyn_capture_config.v1",
        "rom_crc32": str(crc).upper(),
        "rom_size": int(rom_size),
        "platform": platform,
        "pure_jsonl": str(pure_jsonl),
        "out_dir": str(out_dir),
        "memory_domains": domains,
        "default_terminators": profile.get("default_terminators", [0]),
        "autoplay_sequence": profile.get("autoplay_sequence", []),
        "input_scripts": _default_input_scripts(profile.get("autoplay_sequence", [])),
        "glyph_hash_to_char": hash_fontmap,
        "tile_to_char": tile_fontmap,
        "prefer_tile_to_char": bool(prefer_tile_to_char),
        "unknown_char": "?",
        "nametable_bases": hints.get("nametable_bases", [0x3800]),
        "pattern_bases": hints.get("pattern_bases", [0x0000, 0x0800, 0x1000, 0x1800]),
        "tile_cols": int(hints.get("tile_cols", 32)),
        "tile_rows": int(hints.get("tile_rows", 28)),
        "entry_bytes": int(hints.get("entry_bytes", 2)),
        "tile_pattern_bytes": int(hints.get("tile_pattern_bytes", 32)),
        "sample_every_n_frames": int(max(1, sample_every_frames)),
        "sample_every_frames": int(max(1, sample_every_frames)),
        "max_frames": int(max(120, max_frames)),
        "capture_top_candidates": int(max(1, hints.get("capture_top_candidates", 2))),
        "input_explorer_enabled": bool(input_explorer_enabled),
        "input_explorer_switch_frames": int(max(120, input_explorer_switch_frames)),
        "savestate_bfs_enabled": bool(savestate_bfs_enabled),
        "savestate_bfs_depth": int(max(1, savestate_bfs_depth)),
        "savestate_branch_frames": int(max(120, savestate_branch_frames)),
        "savestate_slot_base": int(max(0, savestate_slot_base)),
        "savestate_slot_count": int(max(1, savestate_slot_count)),
        "savestate_seed_slots": seed_slots,
        "fontmap_json_path": str(fontmap_json) if fontmap_json else None,
        "dyn_capture_script_path": str(out_dir / f"{crc}_dyn_capture{suffix}.lua"),
        "dyn_text_log_path": str(out_dir / f"{crc}_dyn_text_log_raw{suffix}.jsonl"),
    }
    return payload


def write_dyn_capture_artifacts(payload: Dict[str, Any]) -> Dict[str, str]:
    out_dir = Path(payload["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = Path(payload["dyn_capture_script_path"])
    config_path = out_dir / f"{payload['rom_crc32']}_runtime_dyn_capture_config.json"
    script_path.write_text(render_dyn_capture_lua(payload), encoding="utf-8")
    write_json(config_path, payload)
    return {
        "dyn_capture_script_path": str(script_path),
        "dyn_capture_config_path": str(config_path),
        "dyn_text_log_path": str(payload["dyn_text_log_path"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera script Lua de captura dinâmica por tilemap/VRAM (BizHawk).")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--platform", default=None, help="Força plataforma")
    ap.add_argument(
        "--fontmap-json",
        default=None,
        help="JSON glyph_hash->char (FNV-1a 32). Aceita tile->char legado como fallback.",
    )
    ap.add_argument("--max-frames", type=int, default=18000, help="Frames máximos")
    ap.add_argument("--sample-every-frames", type=int, default=3, help="Amostragem em frames")
    ap.add_argument(
        "--sample-every-n-frames",
        type=int,
        default=None,
        help="Alias explícito para sample_every_n_frames (prioritário).",
    )
    ap.add_argument("--input-explorer-enabled", type=int, default=0, help="1 para habilitar explorador")
    ap.add_argument("--input-explorer-switch-frames", type=int, default=600, help="Troca de script")
    ap.add_argument("--savestate-bfs-enabled", type=int, default=0, help="1 para habilitar BFS de savestate")
    ap.add_argument("--savestate-bfs-depth", type=int, default=2, help="Profundidade do BFS")
    ap.add_argument("--savestate-branch-frames", type=int, default=900, help="Frames por ramo")
    ap.add_argument("--savestate-slot-base", type=int, default=1, help="Slot base")
    ap.add_argument("--savestate-slot-count", type=int, default=6, help="Quantidade de slots")
    ap.add_argument(
        "--savestate-seed-slots",
        default="",
        help="CSV de slots existentes para pré-ramificação (ex.: 1,2,3,4,5,6).",
    )
    ap.add_argument("--trace-suffix", default="", help="Sufixo de arquivo (cenário)")
    ap.add_argument("--out-base", default=None, help="Base de saída (default: .../out/<CRC>/runtime)")
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl não encontrado: {pure_jsonl}")
    fontmap = Path(args.fontmap_json).expanduser().resolve() if args.fontmap_json else None
    seed_slots: List[int] = []
    for raw in str(args.savestate_seed_slots or "").split(","):
        item = str(raw or "").strip()
        if not item:
            continue
        try:
            val = int(item)
        except Exception:
            continue
        if val < 0:
            continue
        if val not in seed_slots:
            seed_slots.append(val)
    payload = build_dyn_capture_payload(
        pure_jsonl=pure_jsonl,
        platform_hint=args.platform,
        fontmap_json=fontmap,
        max_frames=max(120, int(args.max_frames)),
        sample_every_frames=max(
            1,
            int(
                args.sample_every_n_frames
                if args.sample_every_n_frames is not None
                else args.sample_every_frames
            ),
        ),
        input_explorer_enabled=bool(int(args.input_explorer_enabled or 0)),
        input_explorer_switch_frames=max(120, int(args.input_explorer_switch_frames)),
        savestate_bfs_enabled=bool(int(args.savestate_bfs_enabled or 0)),
        savestate_bfs_depth=max(1, int(args.savestate_bfs_depth)),
        savestate_branch_frames=max(120, int(args.savestate_branch_frames)),
        savestate_slot_base=max(0, int(args.savestate_slot_base)),
        savestate_slot_count=max(1, int(args.savestate_slot_count)),
        savestate_seed_slots=seed_slots,
        trace_suffix=str(args.trace_suffix or ""),
        out_base=Path(args.out_base).expanduser().resolve() if args.out_base else None,
    )
    artifacts = write_dyn_capture_artifacts(payload)
    print(json.dumps(artifacts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
