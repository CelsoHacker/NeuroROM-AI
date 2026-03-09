#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Inferência automática de TBL (Master System / tile text) sem emulador.

Entrada:
- ROM .sms/.gg/.sg (binário)
- {CRC32}_pure_text.jsonl (extraído pelo seu sistema)

Saídas:
- profiles/sms/{CRC32}_tbl_auto.json      (token->char + metadados)
- out/{CRC32}_tbl_auto_report.txt         (relatório)
- out/{CRC32}_decoded_preview.txt         (amostra decodificada)

Como funciona:
1) Decodifica ROM em tiles 8x8 4bpp (32 bytes por tile) -> bitboard 64 bits (binarizado).
2) Detecta "regiões candidatas" de fonte: runs de tiles com densidade de pixels típica de glyph.
3) Faz matching com um alfabeto de referência (A-Z, 0-9, espaço e alguns sinais) por distância (XOR+popcount).
4) Infere se tokens no JSONL são 1 byte ou 2 bytes (heurística).
5) Tenta inferir o "base_tile": tile_index = base_tile + token_value (ou 16-bit).
6) Gera TBL com confiança (só mapeia quando o match é forte).

IMPORTANTE:
- Não garante 100% para toda ROM. Se a fonte estiver comprimida/atípica, reporta baixa confiança.
- Não faz scan de texto ASCII; só analisa tiles.
"""

from __future__ import annotations

import argparse
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional

TOKEN_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")

# -----------------------------
# Utilidades CRC32 / IO
# -----------------------------

def crc32_file(path: Path) -> str:
    crc = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"

def read_jsonl(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"[ERRO] JSON inválido no JSONL linha {ln}: {e}") from e
            if not isinstance(obj, dict):
                raise SystemExit(f"[ERRO] JSONL linha {ln} não é objeto JSON.")
            out.append(obj)
    return out

def extract_tokens_from_item(item: dict) -> List[int]:
    """
    Extrai tokens do item:
    - Preferência: item["tokens"] (lista)
    - Fallback: parse de item["text"] no formato {XX}
    Retorna lista de ints 0..255.
    """
    tokens: List[int] = []
    if "tokens" in item and isinstance(item["tokens"], list):
        for t in item["tokens"]:
            if isinstance(t, int) and 0 <= t <= 255:
                tokens.append(t)
            elif isinstance(t, str):
                s = t.strip().upper().replace("0X", "").replace("{", "").replace("}", "")
                if re.fullmatch(r"[0-9A-F]{2}", s):
                    tokens.append(int(s, 16))
    if tokens:
        return tokens

    txt = item.get("text", "")
    if isinstance(txt, str):
        for m in TOKEN_RE.finditer(txt):
            tokens.append(int(m.group(1), 16))
    return tokens

# -----------------------------
# Inferência de largura do token (1 byte vs 2 bytes)
# -----------------------------

def infer_token_width(token_seqs: List[List[int]]) -> int:
    """
    Heurística:
    - Se muitas sequências têm comprimento par e o byte alto (posição ímpar) é frequentemente 0x00,
      assume 2 bytes little-endian (lo,hi).
    - Senão, assume 1 byte.
    """
    even = 0
    hi_counter = Counter()
    checked = 0

    for seq in token_seqs:
        if len(seq) >= 6 and len(seq) % 2 == 0:
            even += 1
            for i in range(1, len(seq), 2):
                hi_counter[seq[i]] += 1
            checked += 1
        if checked >= 200:
            break

    if even >= 30:
        total_hi = sum(hi_counter.values())
        if total_hi > 0:
            top_hi, top_count = hi_counter.most_common(1)[0]
            # Se o "hi" dominante for 0x00 (ou muito concentrado), é forte indício de 16-bit
            if top_count / total_hi >= 0.75 and top_hi in (0x00, 0x01, 0x02, 0x04, 0x08):
                return 2
    return 1

def tokens_to_values(seq: List[int], width: int) -> List[int]:
    """Converte sequência de bytes em valores: 1 byte -> v; 2 bytes -> lo + (hi<<8) (little-endian)."""
    if width == 1:
        return seq[:]
    vals = []
    for i in range(0, len(seq) - 1, 2):
        vals.append(seq[i] | (seq[i+1] << 8))
    return vals

# -----------------------------
# Tiles SMS 4bpp -> bitboard 64-bit binário
# -----------------------------

def sms_tile_4bpp_to_bitboard(tile32: bytes) -> int:
    """
    Formato VDP SMS: 32 bytes por tile.
    Para cada linha y:
      b0,b1,b2,b3 = 4 bytes (bitplanes)
      pixel = bit0 + bit1<<1 + bit2<<2 + bit3<<3
    Binariza: pixel!=0 => 1
    Retorna bitboard 64-bit: bit (y*8 + x) = 1 se pixel on.
    """
    if len(tile32) != 32:
        raise ValueError("tile32 deve ter 32 bytes")

    bb = 0
    for y in range(8):
        b0 = tile32[y*4 + 0]
        b1 = tile32[y*4 + 1]
        b2 = tile32[y*4 + 2]
        b3 = tile32[y*4 + 3]
        for x in range(8):
            mask = 1 << (7 - x)
            p = ((b0 & mask) != 0) | (((b1 & mask) != 0) << 1) | (((b2 & mask) != 0) << 2) | (((b3 & mask) != 0) << 3)
            if p:
                bb |= 1 << (y*8 + x)
    return bb

def bitboard_ink_ratio(bb: int) -> float:
    """Densidade de pixels ligados (0..1)."""
    return bb.bit_count() / 64.0

# -----------------------------
# Fonte de referência (8x8) - definida aqui (original / simples)
# -----------------------------

def glyph_from_rows(rows: List[str]) -> int:
    """
    rows: 8 strings de 8 chars.
    Usa '#' como pixel ligado, '.' como desligado.
    """
    if len(rows) != 8 or any(len(r) != 8 for r in rows):
        raise ValueError("glyph precisa de 8 linhas de 8 chars")
    bb = 0
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "#":
                bb |= 1 << (y*8 + x)
    return bb

def build_reference_glyphs() -> Dict[str, int]:
    """
    Conjunto mínimo que costuma funcionar bem em menus:
    - Espaço, 0-9, A-Z, '.', ',', '!', '?', '-', ':', '/'
    """
    g: Dict[str, int] = {}

    # Espaço
    g[" "] = glyph_from_rows([
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
    ])

    # Dígitos (5x7 centralizado)
    g["0"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##.###.",
        ".###.##.",
        ".##..##.",
        "..####..",
        "........",
        "........",
    ])
    g["1"] = glyph_from_rows([
        "...##...",
        "..###...",
        "...##...",
        "...##...",
        "...##...",
        "..####..",
        "........",
        "........",
    ])
    g["2"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        "....##..",
        "...##...",
        "..##....",
        ".######.",
        "........",
        "........",
    ])
    g["3"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        "....##..",
        "...###..",
        "....##..",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["4"] = glyph_from_rows([
        "...##...",
        "..###...",
        ".####...",
        ".##.##..",
        ".######.",
        "...##...",
        "...##...",
        "........",
    ])
    g["5"] = glyph_from_rows([
        ".######.",
        ".##.....",
        ".#####..",
        "....##..",
        "....##..",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["6"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##.....",
        ".#####..",
        ".##..##.",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["7"] = glyph_from_rows([
        ".######.",
        "....##..",
        "...##...",
        "..##....",
        "..##....",
        "..##....",
        "..##....",
        "........",
    ])
    g["8"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##..##.",
        "..####..",
        ".##..##.",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["9"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##..##.",
        "..#####.",
        "....##..",
        ".##..##.",
        "..####..",
        "........",
    ])

    # Letras A-Z (simples)
    g["A"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##..##.",
        ".######.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "........",
    ])
    g["B"] = glyph_from_rows([
        ".#####..",
        ".##..##.",
        ".##..##.",
        ".#####..",
        ".##..##.",
        ".##..##.",
        ".#####..",
        "........",
    ])
    g["C"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##.....",
        ".##.....",
        ".##.....",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["D"] = glyph_from_rows([
        ".#####..",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".#####..",
        "........",
    ])
    g["E"] = glyph_from_rows([
        ".######.",
        ".##.....",
        ".##.....",
        ".#####..",
        ".##.....",
        ".##.....",
        ".######.",
        "........",
    ])
    g["F"] = glyph_from_rows([
        ".######.",
        ".##.....",
        ".##.....",
        ".#####..",
        ".##.....",
        ".##.....",
        ".##.....",
        "........",
    ])
    g["G"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##.....",
        ".##.###.",
        ".##..##.",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["H"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".######.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "........",
    ])
    g["I"] = glyph_from_rows([
        "..####..",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "..####..",
        "........",
    ])
    g["J"] = glyph_from_rows([
        "...####.",
        "....##..",
        "....##..",
        "....##..",
        ".##.##..",
        ".##.##..",
        "..###...",
        "........",
    ])
    g["K"] = glyph_from_rows([
        ".##..##.",
        ".##.##..",
        ".####...",
        ".###....",
        ".####...",
        ".##.##..",
        ".##..##.",
        "........",
    ])
    g["L"] = glyph_from_rows([
        ".##.....",
        ".##.....",
        ".##.....",
        ".##.....",
        ".##.....",
        ".##.....",
        ".######.",
        "........",
    ])
    g["M"] = glyph_from_rows([
        ".##...#.",
        ".###.##.",
        ".######.",
        ".##.###.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "........",
    ])
    g["N"] = glyph_from_rows([
        ".##..##.",
        ".###.##.",
        ".######.",
        ".##.###.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "........",
    ])
    g["O"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["P"] = glyph_from_rows([
        ".#####..",
        ".##..##.",
        ".##..##.",
        ".#####..",
        ".##.....",
        ".##.....",
        ".##.....",
        "........",
    ])
    g["Q"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##.###.",
        ".##..##.",
        "..#####.",
        "........",
    ])
    g["R"] = glyph_from_rows([
        ".#####..",
        ".##..##.",
        ".##..##.",
        ".#####..",
        ".####...",
        ".##.##..",
        ".##..##.",
        "........",
    ])
    g["S"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        ".##.....",
        "..####..",
        "....##..",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["T"] = glyph_from_rows([
        ".######.",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "........",
    ])
    g["U"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "..####..",
        "........",
    ])
    g["V"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##..##.",
        "..####..",
        "...##...",
        "........",
    ])
    g["W"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        ".##..##.",
        ".##.###.",
        ".######.",
        ".###.##.",
        ".##...#.",
        "........",
    ])
    g["X"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        "..####..",
        "...##...",
        "..####..",
        ".##..##.",
        ".##..##.",
        "........",
    ])
    g["Y"] = glyph_from_rows([
        ".##..##.",
        ".##..##.",
        "..####..",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "........",
    ])
    g["Z"] = glyph_from_rows([
        ".######.",
        "....##..",
        "...##...",
        "..##....",
        ".##.....",
        ".##.....",
        ".######.",
        "........",
    ])

    # Pontuação básica
    g["."] = glyph_from_rows([
        "........",
        "........",
        "........",
        "........",
        "........",
        "...##...",
        "...##...",
        "........",
    ])
    g[","] = glyph_from_rows([
        "........",
        "........",
        "........",
        "........",
        "........",
        "...##...",
        "...##...",
        "..##....",
    ])
    g["!"] = glyph_from_rows([
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "........",
        "...##...",
        "........",
    ])
    g["?"] = glyph_from_rows([
        "..####..",
        ".##..##.",
        "....##..",
        "...##...",
        "...##...",
        "........",
        "...##...",
        "........",
    ])
    g["-"] = glyph_from_rows([
        "........",
        "........",
        "........",
        ".######.",
        "........",
        "........",
        "........",
        "........",
    ])
    g[":"] = glyph_from_rows([
        "........",
        "...##...",
        "...##...",
        "........",
        "........",
        "...##...",
        "...##...",
        "........",
    ])
    g["/"] = glyph_from_rows([
        ".....##.",
        "....##..",
        "...##...",
        "..##....",
        ".##.....",
        "##......",
        "........",
        "........",
    ])

    return g

# -----------------------------
# Matching (XOR + popcount)
# -----------------------------

def best_match_char(tile_bb: int, ref: Dict[str, int]) -> Tuple[str, int]:
    """
    Retorna (char, dist) com menor distância (bits diferentes).
    """
    best_c = "?"
    best_d = 9999
    for c, bb in ref.items():
        d = (tile_bb ^ bb).bit_count()
        if d < best_d:
            best_d = d
            best_c = c
    return best_c, best_d

@dataclass
class RegionScore:
    start_tile: int
    length: int
    matched: int
    avg_dist: float
    score: float

# -----------------------------
# Encontrar regiões candidatas de fonte
# -----------------------------

def find_candidate_regions(tile_bbs: List[int],
                           min_run: int = 64,
                           min_ink: float = 0.05,
                           max_ink: float = 0.35) -> List[Tuple[int, int]]:
    """
    Procura runs consecutivos de tiles com densidade típica de fonte.
    Retorna lista de (start_tile, length).
    """
    regions = []
    run_start = None
    run_len = 0

    for i, bb in enumerate(tile_bbs):
        ink = bitboard_ink_ratio(bb)
        ok = (min_ink <= ink <= max_ink)
        if ok:
            if run_start is None:
                run_start = i
                run_len = 1
            else:
                run_len += 1
        else:
            if run_start is not None and run_len >= min_run:
                regions.append((run_start, run_len))
            run_start = None
            run_len = 0

    if run_start is not None and run_len >= min_run:
        regions.append((run_start, run_len))

    return regions

def score_region(tile_bbs: List[int],
                 start: int,
                 length: int,
                 ref: Dict[str, int],
                 dist_threshold: int = 14,
                 max_tiles_eval: int = 512) -> Tuple[RegionScore, Dict[int, Tuple[str, int]]]:
    """
    Avalia uma região: quantos tiles batem bem com o alfabeto de referência.
    """
    end = min(start + length, len(tile_bbs))
    mapping: Dict[int, Tuple[str, int]] = {}
    matched = 0
    dist_sum = 0
    eval_count = 0

    # Avalia no máximo max_tiles_eval (para velocidade)
    for t in range(start, end):
        c, d = best_match_char(tile_bbs[t], ref)
        eval_count += 1
        if d <= dist_threshold:
            matched += 1
            dist_sum += d
            mapping[t] = (c, d)

        if eval_count >= max_tiles_eval:
            break

    avg_dist = (dist_sum / matched) if matched else 999.0
    # score combina match e qualidade
    score = matched - (avg_dist * 0.25 if matched else 0)

    return RegionScore(start, end - start, matched, avg_dist, score), mapping

# -----------------------------
# Inferir base_tile e construir TBL
# -----------------------------

def infer_best_base(token_freq: Counter,
                    token_width: int,
                    region_start: int,
                    region_len: int,
                    tile_to_char: Dict[int, Tuple[str, int]],
                    dist_threshold: int = 14) -> Tuple[int, float]:
    """
    Procura um base_tile tal que base_tile + token_value cai dentro da região e bate com char conhecido.
    Tenta base em uma janela de 0..255 atrás do region_start.
    Retorna (best_base, best_score_norm).
    """
    top_tokens = [tv for tv, _ in token_freq.most_common(80)]
    best_base = region_start
    best = -1.0

    # janela pequena: region_start-255..region_start
    for base in range(max(0, region_start - 255), region_start + 1):
        ok = 0
        seen = 0
        for tv in top_tokens:
            seen += 1
            tile_idx = base + tv
            if region_start <= tile_idx < region_start + region_len:
                if tile_idx in tile_to_char:
                    c, d = tile_to_char[tile_idx]
                    if c != "?" and d <= dist_threshold:
                        ok += 1
        score_norm = ok / max(seen, 1)
        if score_norm > best:
            best = score_norm
            best_base = base

    return best_base, best

def build_tbl_map(token_freq: Counter,
                  token_width: int,
                  base_tile: int,
                  region_start: int,
                  region_len: int,
                  tile_to_char: Dict[int, Tuple[str, int]],
                  dist_threshold: int = 14) -> Dict[str, str]:
    """
    Constrói mapa token_hex -> char
    (Para token_width=1: "3A" -> "A")
    (Para token_width=2: usa valor 16-bit em hex 4 chars)
    """
    tbl: Dict[str, str] = {}
    for tv, _ in token_freq.most_common():
        tile_idx = base_tile + tv
        if not (region_start <= tile_idx < region_start + region_len):
            continue
        if tile_idx not in tile_to_char:
            continue
        c, d = tile_to_char[tile_idx]
        if c == "?" or d > dist_threshold:
            continue
        if token_width == 1:
            tbl[f"{tv:02X}"] = c
        else:
            tbl[f"{tv:04X}"] = c
    return tbl

def decode_preview(items: List[dict],
                   token_width: int,
                   tbl: Dict[str, str],
                   limit: int = 25) -> List[str]:
    """
    Decodifica alguns itens em preview, mantendo tokens desconhecidos como {XX}/{XXXX}.
    """
    lines = []
    shown = 0
    for it in items:
        seq = extract_tokens_from_item(it)
        if not seq:
            continue
        vals = tokens_to_values(seq, token_width)
        out = []
        for v in vals:
            key = f"{v:02X}" if token_width == 1 else f"{v:04X}"
            if key in tbl:
                out.append(tbl[key])
            else:
                # preserva como token para auditoria
                out.append("{" + key + "}")
        off = it.get("offset_hex") or it.get("offset") or "?"
        lines.append(f"@{off} " + "".join(out))
        shown += 1
        if shown >= limit:
            break
    return lines

# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, help="Caminho ROM (.sms/.gg/.sg)")
    ap.add_argument("--pure-text", required=True, help="Caminho {CRC32}_pure_text.jsonl")
    ap.add_argument("--profiles-dir", default="profiles/sms", help="Diretório profiles/sms")
    ap.add_argument("--out-dir", default="out", help="Diretório out/")
    ap.add_argument("--dist-threshold", type=int, default=14, help="Máx distância para aceitar match (menor = mais rígido)")
    args = ap.parse_args()

    rom_path = Path(args.rom)
    pure_path = Path(args.pure_text)
    profiles_dir = Path(args.profiles_dir)
    out_dir = Path(args.out_dir)

    profiles_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    rom = rom_path.read_bytes()
    rom_size = len(rom)
    crc = crc32_file(rom_path)

    items = read_jsonl(pure_path)

    # Coleta sequências de tokens
    token_seqs = []
    token_freq_1b = Counter()
    for it in items:
        seq = extract_tokens_from_item(it)
        if not seq:
            continue
        token_seqs.append(seq)
        for b in seq:
            token_freq_1b[b] += 1

    if not token_seqs:
        raise SystemExit("[ERRO] Não encontrei tokens {XX} (nem campo tokens[]) no pure_text.jsonl.")

    token_width = infer_token_width(token_seqs)

    # Frequência em valores (se 16-bit)
    if token_width == 2:
        token_freq = Counter()
        for seq in token_seqs:
            vals = tokens_to_values(seq, 2)
            for v in vals:
                token_freq[v] += 1
    else:
        token_freq = token_freq_1b

    # Pré-computa tiles (32 bytes por tile)
    if rom_size < 32:
        raise SystemExit("[ERRO] ROM pequena demais.")
    tile_count = rom_size // 32
    tile_bbs = [sms_tile_4bpp_to_bitboard(rom[i*32:(i+1)*32]) for i in range(tile_count)]

    ref = build_reference_glyphs()

    # Encontra regiões candidatas
    regions = find_candidate_regions(tile_bbs, min_run=64, min_ink=0.05, max_ink=0.35)
    if not regions:
        raise SystemExit("[ERRO] Não encontrei região candidata de fonte (tiles com densidade típica). Provável compressão/format diferente.")

    # Score das regiões
    scored: List[Tuple[RegionScore, Dict[int, Tuple[str, int]]]] = []
    for start, length in regions[:50]:  # limita para não ficar lento em ROMs grandes
        rs, tilemap = score_region(tile_bbs, start, length, ref, dist_threshold=args.dist_threshold, max_tiles_eval=512)
        scored.append((rs, tilemap))

    scored.sort(key=lambda x: x[0].score, reverse=True)
    best_rs, best_tilemap = scored[0]

    # Infer base_tile
    best_base, base_conf = infer_best_base(token_freq, token_width, best_rs.start_tile, best_rs.length, best_tilemap, dist_threshold=args.dist_threshold)

    # Constrói TBL
    tbl = build_tbl_map(token_freq, token_width, best_base, best_rs.start_tile, best_rs.length, best_tilemap, dist_threshold=args.dist_threshold)

    # Preview
    preview_lines = decode_preview(items, token_width, tbl, limit=30)

    # Saídas
    tbl_out = profiles_dir / f"{crc}_tbl_auto.json"
    report_out = out_dir / f"{crc}_tbl_auto_report.txt"
    preview_out = out_dir / f"{crc}_decoded_preview.txt"

    payload = {
        "crc32": crc,
        "rom_size": rom_size,
        "token_width_bytes": token_width,
        "region": {
            "start_tile": best_rs.start_tile,
            "length_tiles": best_rs.length,
            "matched_tiles": best_rs.matched,
            "avg_dist": best_rs.avg_dist,
            "score": best_rs.score,
        },
        "base_tile": best_base,
        "base_confidence": base_conf,
        "dist_threshold": args.dist_threshold,
        "tbl_map": tbl,
        "stats": {
            "unique_tokens": len(token_freq),
            "mapped_tokens": len(tbl),
        },
        "notes": [
            "tbl_map só inclui matches fortes; tokens não mapeados ficam fora (fail-fast).",
            "Se mapped_tokens for muito baixo, fonte pode estar comprimida ou tokens não são IDs diretos de tile.",
        ]
    }

    tbl_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_lines = [
        f"[ROM] CRC32={crc} ROM_SIZE={rom_size}",
        f"[TOKENS] token_width_bytes={token_width} unique_tokens={len(token_freq)} mapped_tokens={len(tbl)}",
        f"[FONT_REGION] start_tile={best_rs.start_tile} length_tiles={best_rs.length} matched={best_rs.matched} avg_dist={best_rs.avg_dist:.2f} score={best_rs.score:.2f}",
        f"[BASE] base_tile={best_base} base_confidence={base_conf:.3f}",
        "",
        "[PREVIEW]",
        *preview_lines,
        "",
        "[NEXT]",
        "- Se o preview já ficou legível: use este tbl_auto.json no seu pipeline (por CRC32).",
        "- Se ficou quase tudo {XX}: aumente dist_threshold para 16-18 (menos rígido) OU a fonte está comprimida/format diferente.",
    ]
    report_out.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    preview_out.write_text("\n".join(preview_lines) + "\n", encoding="utf-8")

    print(f"[OK] TBL: {tbl_out}")
    print(f"[OK] REPORT: {report_out}")
    print(f"[OK] PREVIEW: {preview_out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
