# -*- coding: utf-8 -*-
"""
FONT TOOLS - Backend para manipulacao de fontes de ROMs retro
==============================================================
Gera glifos acentuados PT-BR a partir de glifos base existentes.
Suporta 1bpp (SMS/NES) e 4bpp (SNES/SMS VDP2).

Autor: ROM Translation Framework v6.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path


@dataclass
class FontGlyph:
    """Representa um glifo (8x8 pixels)."""
    char: str
    tile_index: int
    pixels: List[int] = field(default_factory=lambda: [0] * 64)
    bpp: int = 1  # 1 = monocromo (on/off), 4 = 16 cores


class FontMap:
    """Mapa de fontes: carrega, modifica e salva glifos de uma ROM."""

    def __init__(self, rom_data: bytearray, font_offset: int = 0,
                 bpp: int = 1, num_tiles: int = 256):
        self.rom_data = rom_data
        self.font_offset = font_offset
        self.bpp = bpp
        self.num_tiles = num_tiles
        self.bytes_per_tile = 8 * bpp  # 1bpp=8, 4bpp=32
        self.glyphs: Dict[int, FontGlyph] = {}
        self._load_glyphs()

    def _load_glyphs(self):
        """Carrega todos os glifos do offset da fonte."""
        for i in range(self.num_tiles):
            offset = self.font_offset + i * self.bytes_per_tile
            end = offset + self.bytes_per_tile
            if end > len(self.rom_data):
                break
            tile_bytes = self.rom_data[offset:end]
            pixels = self._decode_tile(tile_bytes)
            self.glyphs[i] = FontGlyph(char="", tile_index=i, pixels=pixels, bpp=self.bpp)

    def _decode_tile(self, tile_bytes: bytes) -> List[int]:
        """Decodifica tile de ROM para pixels 8x8."""
        if self.bpp == 1:
            return self._decode_1bpp(tile_bytes)
        elif self.bpp == 4:
            return self._decode_4bpp(tile_bytes)
        return [0] * 64

    def _decode_1bpp(self, tile_bytes: bytes) -> List[int]:
        """Decodifica tile 1bpp (8 bytes = 8 linhas, 1 bit por pixel)."""
        pixels = [0] * 64
        if len(tile_bytes) < 8:
            return pixels
        for y in range(8):
            byte_val = tile_bytes[y]
            for x in range(8):
                bit = 7 - x
                pixels[y * 8 + x] = (byte_val >> bit) & 1
        return pixels

    def _decode_4bpp(self, tile_bytes: bytes) -> List[int]:
        """Decodifica tile 4bpp (32 bytes)."""
        pixels = [0] * 64
        if len(tile_bytes) < 32:
            return pixels
        for y in range(8):
            p0 = tile_bytes[y * 2]
            p1 = tile_bytes[y * 2 + 1]
            p2 = tile_bytes[16 + y * 2]
            p3 = tile_bytes[16 + y * 2 + 1]
            for x in range(8):
                bit = 7 - x
                val = (((p3 >> bit) & 1) << 3) | (((p2 >> bit) & 1) << 2) | \
                      (((p1 >> bit) & 1) << 1) | ((p0 >> bit) & 1)
                pixels[y * 8 + x] = val
        return pixels

    def _encode_tile(self, pixels: List[int]) -> bytearray:
        """Codifica pixels 8x8 de volta para bytes de tile."""
        if self.bpp == 1:
            return self._encode_1bpp(pixels)
        elif self.bpp == 4:
            return self._encode_4bpp(pixels)
        return bytearray(self.bytes_per_tile)

    def _encode_1bpp(self, pixels: List[int]) -> bytearray:
        """Codifica tile 1bpp."""
        tile_bytes = bytearray(8)
        for y in range(8):
            byte_val = 0
            for x in range(8):
                if pixels[y * 8 + x]:
                    byte_val |= (1 << (7 - x))
            tile_bytes[y] = byte_val
        return tile_bytes

    def _encode_4bpp(self, pixels: List[int]) -> bytearray:
        """Codifica tile 4bpp."""
        tile_bytes = bytearray(32)
        for y in range(8):
            p0 = p1 = p2 = p3 = 0
            for x in range(8):
                c = pixels[y * 8 + x]
                bit = 7 - x
                p0 |= ((c >> 0) & 1) << bit
                p1 |= ((c >> 1) & 1) << bit
                p2 |= ((c >> 2) & 1) << bit
                p3 |= ((c >> 3) & 1) << bit
            tile_bytes[y * 2] = p0
            tile_bytes[y * 2 + 1] = p1
            tile_bytes[16 + y * 2] = p2
            tile_bytes[16 + y * 2 + 1] = p3
        return tile_bytes

    def get_glyph(self, index: int) -> Optional[FontGlyph]:
        return self.glyphs.get(index)

    def set_glyph(self, index: int, pixels: List[int], char: str = ""):
        """Atualiza glifo no mapa e na ROM."""
        if index not in self.glyphs:
            self.glyphs[index] = FontGlyph(char=char, tile_index=index,
                                           pixels=list(pixels), bpp=self.bpp)
        else:
            self.glyphs[index].pixels = list(pixels)
            if char:
                self.glyphs[index].char = char

        tile_bytes = self._encode_tile(pixels)
        offset = self.font_offset + index * self.bytes_per_tile
        self.rom_data[offset:offset + self.bytes_per_tile] = tile_bytes

    def find_free_tile_slots(self, start: int = 0x80, end: int = 0xFF) -> List[int]:
        """Busca tiles vazios (todos pixels = 0) no range especificado."""
        free = []
        for i in range(start, min(end + 1, self.num_tiles)):
            glyph = self.glyphs.get(i)
            if glyph and all(p == 0 for p in glyph.pixels):
                free.append(i)
        return free

    def is_tile_empty(self, index: int) -> bool:
        glyph = self.glyphs.get(index)
        if not glyph:
            return True
        return all(p == 0 for p in glyph.pixels)

    def export_tbl(self, output_path: str, char_map: Dict[int, str]):
        """Gera arquivo .tbl com mapeamento byte->caractere."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Tabela de caracteres - Font Editor PT-BR\n")
            f.write("# Formato: HEX=CHAR\n")
            f.write("# Gerado automaticamente pelo Font Editor\n\n")
            for byte_val in sorted(char_map.keys()):
                char = char_map[byte_val]
                if char == '\n':
                    char = '\\n'
                f.write(f"{byte_val:02X}={char}\n")


# ============================================================================
# ACCENT GENERATION ENGINE
# ============================================================================

# Overlays de acentos (8 pixels de largura, posicao relativa ao topo do glifo)
# 1 = pixel ligado, 0 = pixel desligado
# Cada overlay cobre as linhas 0-1 do glifo (topo)

ACCENT_OVERLAYS = {
    'tilde': [  # til (~)
        [0, 0, 1, 1, 0, 1, 0, 0],
        [0, 1, 0, 0, 1, 1, 0, 0],
    ],
    'acute': [  # agudo (')
        [0, 0, 0, 1, 1, 0, 0, 0],
        [0, 0, 1, 0, 0, 0, 0, 0],
    ],
    'grave': [  # grave (`)
        [0, 0, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0],
    ],
    'circumflex': [  # circunflexo (^)
        [0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 1, 0, 1, 0, 0, 0],
    ],
    'cedilla': [  # cedilha - aplicada na parte inferior, nao no topo
        [0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0],
    ],
    'umlaut': [  # trema
        [0, 0, 1, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ],
}

# Receitas: char_acentuado -> (char_base, tipo_de_acento)
ACCENT_RECIPES: Dict[str, Tuple[str, str]] = {
    # Minusculas
    'a\u0303': ('a', 'tilde'),   # ã
    'a\u0301': ('a', 'acute'),   # á
    'a\u0300': ('a', 'grave'),   # à
    'a\u0302': ('a', 'circumflex'),  # â
    'e\u0301': ('e', 'acute'),   # é
    'e\u0302': ('e', 'circumflex'),  # ê
    'i\u0301': ('i', 'acute'),   # í
    'o\u0301': ('o', 'acute'),   # ó
    'o\u0302': ('o', 'circumflex'),  # ô
    'o\u0303': ('o', 'tilde'),   # õ
    'u\u0301': ('u', 'acute'),   # ú
    'c\u0327': ('c', 'cedilla'), # ç
    # Maiusculas
    'A\u0303': ('A', 'tilde'),
    'A\u0301': ('A', 'acute'),
    'A\u0300': ('A', 'grave'),
    'A\u0302': ('A', 'circumflex'),
    'E\u0301': ('E', 'acute'),
    'E\u0302': ('E', 'circumflex'),
    'I\u0301': ('I', 'acute'),
    'O\u0301': ('O', 'acute'),
    'O\u0302': ('O', 'circumflex'),
    'O\u0303': ('O', 'tilde'),
    'U\u0301': ('U', 'acute'),
    'C\u0327': ('C', 'cedilla'),
}

# Mapeamento mais amigavel usando caracteres compostos NFC
import unicodedata

PTBR_ACCENTED_CHARS: Dict[str, Tuple[str, str]] = {}
for decomposed, (base, accent_type) in ACCENT_RECIPES.items():
    composed = unicodedata.normalize('NFC', decomposed)
    PTBR_ACCENTED_CHARS[composed] = (base, accent_type)


def generate_accented_glyph(base_pixels: List[int], accent_type: str,
                            ink_color: int = 1) -> List[int]:
    """
    Gera glifo acentuado a partir de glifo base.

    Algoritmo:
    - Para acentos no topo (tilde, acute, grave, circumflex, umlaut):
      1. Desloca glifo base 1px para baixo
      2. Aplica overlay do acento nas linhas 0-1
    - Para cedilha:
      1. Nao desloca (usa glifo base como esta)
      2. Aplica overlay nas linhas 6-7 (parte inferior)
    """
    overlay = ACCENT_OVERLAYS.get(accent_type)
    if not overlay:
        return list(base_pixels)

    result = [0] * 64

    if accent_type == 'cedilla':
        # Cedilha: nao desloca, adiciona gancho embaixo
        for i in range(64):
            result[i] = base_pixels[i]
        # Aplica cedilha nas linhas 6-7
        for row_idx, row in enumerate(overlay):
            y = 6 + row_idx
            if y >= 8:
                break
            for x in range(8):
                if row[x]:
                    result[y * 8 + x] = ink_color
    else:
        # Acento no topo: desloca base 1px para baixo
        for y in range(7, 0, -1):
            for x in range(8):
                result[y * 8 + x] = base_pixels[(y - 1) * 8 + x]
        # Limpa linha 0 (vai receber o acento)
        for x in range(8):
            result[x] = 0
        # Aplica overlay do acento
        for row_idx, row in enumerate(overlay):
            y = row_idx
            for x in range(8):
                if row[x]:
                    result[y * 8 + x] = ink_color

    return result


def generate_all_ptbr_accents(font_map: FontMap,
                              ascii_base_offset: int = 0x20,
                              ink_color: int = 1,
                              fallback_slots: Optional[List[int]] = None,
                              target_chars: Optional[set[str]] = None) -> Dict[str, Tuple[int, List[int]]]:
    """
    Gera todos os glifos acentuados PT-BR.

    Args:
        font_map: FontMap com glifos carregados
        ascii_base_offset: Offset do caractere ' ' (0x20) na tabela de tiles.
                          'a' = ascii_base_offset + (ord('a') - 0x20)
        ink_color: Cor do pixel "ligado" (1 para 1bpp, 15 para 4bpp)

    Returns:
        Dict[char_acentuado, (tile_index_sugerido, pixels)]
    """
    free_slots = font_map.find_free_tile_slots()
    # Fallback: quando não houver tiles vazios, permite sobrescrever slots
    # conhecidos como "baixa prioridade" para habilitar acentos PT-BR.
    fallback_pool: List[int] = []
    if fallback_slots:
        seen_slots = set()
        for slot in fallback_slots:
            if not isinstance(slot, int):
                continue
            if slot < 0 or slot >= font_map.num_tiles:
                continue
            if slot in seen_slots:
                continue
            seen_slots.add(slot)
            if slot not in free_slots:
                fallback_pool.append(slot)
    candidate_slots = list(free_slots) + fallback_pool
    results: Dict[str, Tuple[int, List[int]]] = {}
    slot_idx = 0

    for accented_char, (base_char, accent_type) in PTBR_ACCENTED_CHARS.items():
        if target_chars is not None and accented_char not in target_chars:
            continue
        # Calcula tile index do caractere base
        base_tile = ascii_base_offset + (ord(base_char) - 0x20)
        base_glyph = font_map.get_glyph(base_tile)
        if not base_glyph:
            continue

        if font_map.is_tile_empty(base_tile):
            continue

        accented_pixels = generate_accented_glyph(base_glyph.pixels, accent_type,
                                                  ink_color=ink_color)

        if slot_idx < len(candidate_slots):
            target_tile = candidate_slots[slot_idx]
            slot_idx += 1
        else:
            # Sem slot disponível: não gera este acento.
            continue

        results[accented_char] = (target_tile, accented_pixels)

    return results


def apply_accents_to_fontmap(font_map: FontMap,
                             accents: Dict[str, Tuple[int, List[int]]]) -> Dict[int, str]:
    """
    Aplica glifos acentuados gerados ao FontMap.

    Returns:
        Dict[tile_index, char] para gerar .tbl
    """
    tbl_entries: Dict[int, str] = {}

    for accented_char, (tile_index, pixels) in accents.items():
        if tile_index < font_map.num_tiles:
            font_map.set_glyph(tile_index, pixels, char=accented_char)
            tbl_entries[tile_index] = accented_char

    return tbl_entries
