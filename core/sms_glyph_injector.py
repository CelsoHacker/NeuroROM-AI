# -*- coding: utf-8 -*-
"""
SMS Glyph Injector - Injeção automática de glifos PT-BR em ROMs SMS
====================================================================
Detecta caracteres faltantes no JSONL traduzido vs TBL, gera tiles
acentuados e injeta na região de fonte da ROM.

Requer: font_regions definido em game_profiles_db.json para o CRC32.
Sem scan cego — usa apenas perfis/offsets conhecidos.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .font_tools import (
    FontMap,
    PTBR_ACCENTED_CHARS,
    apply_accents_to_fontmap,
    generate_all_ptbr_accents,
)
from .tbl_loader import TBLLoader

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROFILES_DB_PATH = os.path.join(os.path.dirname(__file__), "game_profiles_db.json")

# Characters that are control/token and should NOT count as missing
_IGNORE_CHARS = set("\n\r\t\x00")
_TOKEN_RE = re.compile(r"\{B:[0-9A-Fa-f]{2}\}")


def _sha256_region(data: bytes, offset: int, size: int) -> str:
    """SHA-256 hex digest of a ROM region."""
    return hashlib.sha256(data[offset:offset + size]).hexdigest()


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _load_game_profile(crc32: str) -> Optional[Dict[str, Any]]:
    """Load game profile from game_profiles_db.json by CRC32."""
    if not os.path.isfile(_PROFILES_DB_PATH):
        return None
    try:
        with open(_PROFILES_DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        for game in db.get("games", []):
            if str(game.get("crc32", "")).upper() == str(crc32).upper():
                return game
    except Exception:
        pass
    return None


def _get_font_regions(profile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract font_regions list from a game profile (may be empty)."""
    if not profile:
        return []
    regions = profile.get("font_regions", [])
    if not isinstance(regions, list):
        return []
    return [r for r in regions if isinstance(r, dict) and r.get("offset") is not None]


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SMSGlyphInjector:
    """
    Injects PT-BR accented glyphs into an SMS ROM's font region.

    Workflow:
        1. detect_missing_chars() — chars in translated JSONL not in TBL
        2. inject_glyphs()        — generate tiles, patch ROM, update TBL
        3. get_report()           — audit trail for proof/report
    """

    def __init__(
        self,
        rom_data: bytearray,
        crc32: str,
        rom_size: int = 0,
        font_hint: str = "",
    ):
        self.rom_data = rom_data
        self.crc32 = str(crc32).upper().strip()
        self.rom_size = rom_size or len(rom_data)
        self._font_hint = str(font_hint or "").strip()
        self._profile = _load_game_profile(self.crc32)
        self._font_regions = _get_font_regions(self._profile)
        self._report: Dict[str, Any] = {}

    def _extract_region_slots(self, region: Dict[str, Any]) -> List[int]:
        """Lê lista de slots candidatos para overwrite controlado de glyphs."""
        slots_raw = (
            region.get("accent_slots")
            or region.get("fallback_slots")
            or region.get("overwrite_slots")
            or []
        )
        if not isinstance(slots_raw, list):
            return []
        slots: List[int] = []
        for item in slots_raw:
            try:
                val = int(item)
            except Exception:
                continue
            if 0 <= val <= 0xFF:
                slots.append(val)
        return slots

    def _load_verdana_font(self) -> Tuple[Optional[Any], str]:
        """
        Carrega fonte Verdana (ou fallback compatível) para rasterizar glyph 8x8.
        Retorna (font_obj, nome_fonte_usada).
        """
        if ImageFont is None:
            return None, ""

        env_font = str(os.environ.get("NEUROROM_GLYPH_FONT", "") or "").strip()
        candidates: List[str] = []
        if self._font_hint:
            candidates.append(self._font_hint)
        if env_font:
            candidates.append(env_font)
        candidates.extend(
            [
                "Verdana.ttf",
                "verdana.ttf",
                "C:/Windows/Fonts/verdana.ttf",
                "C:/Windows/Fonts/verdanab.ttf",
                "DejaVuSans.ttf",
                "Arial.ttf",
            ]
        )
        seen = set()
        for font_name in candidates:
            if not font_name or font_name in seen:
                continue
            seen.add(font_name)
            for size in (10, 9, 11, 8, 12):
                try:
                    return ImageFont.truetype(font_name, size=size), font_name
                except Exception:
                    continue
        try:
            return ImageFont.load_default(), "PIL_DEFAULT"
        except Exception:
            return None, ""

    def _render_char_tile_from_font(
        self,
        ch: str,
        font_obj: Any,
        ink_color: int,
    ) -> Optional[List[int]]:
        """Rasteriza um caractere para tile 8x8 monocromático."""
        if not ch or len(ch) != 1:
            return None
        if Image is None or ImageDraw is None or font_obj is None:
            return None
        try:
            canvas = Image.new("L", (8, 8), 0)
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), ch, font=font_obj)
            if not bbox:
                return None
            w = max(1, int(bbox[2] - bbox[0]))
            h = max(1, int(bbox[3] - bbox[1]))
            x = int((8 - w) // 2) - int(bbox[0])
            y = int((8 - h) // 2) - int(bbox[1])
            draw.text((x, y), ch, fill=255, font=font_obj)
            pixels: List[int] = []
            has_ink = False
            for py in range(8):
                for px in range(8):
                    val = canvas.getpixel((px, py))
                    on = 1 if int(val) >= 100 else 0
                    if on:
                        has_ink = True
                    pixels.append(ink_color if on else 0)
            if not has_ink:
                return None
            return pixels
        except Exception:
            return None

    def _generate_verdana_glyphs(
        self,
        target_chars: Set[str],
        font_map: FontMap,
        region: Dict[str, Any],
        used_tiles: Set[int],
        ink_color: int,
    ) -> Tuple[Dict[str, Tuple[int, List[int]]], str]:
        """
        Gera glifos diretamente da fonte Verdana para chars sem base confiável.
        """
        if not target_chars:
            return {}, ""
        font_obj, font_name = self._load_verdana_font()
        if font_obj is None:
            return {}, ""

        preferred_slots = self._extract_region_slots(region)
        free_slots = font_map.find_free_tile_slots()
        candidate_slots: List[int] = []
        for slot in free_slots + preferred_slots:
            if slot in used_tiles:
                continue
            if slot in candidate_slots:
                continue
            if slot < 0 or slot >= font_map.num_tiles:
                continue
            candidate_slots.append(slot)

        result: Dict[str, Tuple[int, List[int]]] = {}
        slot_idx = 0
        for ch in sorted(target_chars):
            if slot_idx >= len(candidate_slots):
                break
            pix = self._render_char_tile_from_font(ch, font_obj=font_obj, ink_color=ink_color)
            if not pix:
                continue
            slot = candidate_slots[slot_idx]
            slot_idx += 1
            used_tiles.add(slot)
            result[ch] = (slot, pix)
        return result, font_name

    # ------------------------------------------------------------------
    # Step 1: detect missing chars
    # ------------------------------------------------------------------

    def detect_missing_chars(
        self,
        translated_jsonl_path: str,
        tbl: TBLLoader,
    ) -> Set[str]:
        """
        Scan translated JSONL and return chars that have no TBL mapping.

        Ignores control chars, byte tokens {B:XX}, and whitespace.
        """
        all_chars: Set[str] = set()

        try:
            with open(translated_jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    dst = str(
                        row.get("text_dst")
                        or row.get("translated_text")
                        or row.get("translation")
                        or row.get("translated")
                        or row.get("dst")
                        or row.get("text")
                        or ""
                    )
                    dst = unicodedata.normalize("NFC", dst)
                    # Remove byte tokens before scanning
                    dst_clean = _TOKEN_RE.sub("", dst)
                    for ch in dst_clean:
                        if ch not in _IGNORE_CHARS and not ch.isspace():
                            all_chars.add(ch)
        except FileNotFoundError:
            return set()

        # Check which chars have no reverse mapping in TBL
        reverse = getattr(tbl, "reverse_map", {})
        missing: Set[str] = set()
        for ch in all_chars:
            code = ord(ch)
            # Standard ASCII printable (32-126) — always supported
            if 32 <= code <= 126:
                continue
            # Check TBL
            if ch in reverse:
                continue
            missing.add(ch)

        return missing

    def needs_font_tile_injection(self, tbl: TBLLoader) -> bool:
        """
        Check if TBL has accent mappings that reference tiles without
        proper glyph data in the ROM.  Returns True if injection is needed.
        """
        if not self._font_regions:
            return False
        region = self._font_regions[0]
        offset_raw = region.get("offset", 0)
        font_offset = int(offset_raw, 16) if isinstance(offset_raw, str) else int(offset_raw)
        bpp = int(region.get("bpp", 1))
        bytes_per_tile = 8 * bpp

        reverse = getattr(tbl, "reverse_map", {})
        for ch in PTBR_ACCENTED_CHARS:
            seq = reverse.get(ch)
            if seq is None or len(seq) != 1:
                continue
            tile_idx = seq[0]
            tile_off = font_offset + tile_idx * bytes_per_tile
            if tile_off + bytes_per_tile > len(self.rom_data):
                return True
            tile = self.rom_data[tile_off:tile_off + bytes_per_tile]
            # If tile is empty (all zeros) or all-filled (0xFF), the glyph is missing
            if all(b == 0 for b in tile) or all(b == 0xFF for b in tile):
                return True
        return False

    # ------------------------------------------------------------------
    # Step 2: inject glyphs
    # ------------------------------------------------------------------

    def inject_glyphs(
        self,
        missing_chars: Set[str],
        tbl: TBLLoader,
    ) -> Dict[str, Any]:
        """
        Inject PT-BR glyph tiles into ROM font region and update TBL.

        Returns dict with:
            success: bool
            injected_count: int
            missing_before: list of chars
            missing_after: list of chars
            tbl_updates: dict {char: hex_byte}
            sha256_before: str
            sha256_after: str
            error: str (if failed)
        """
        result: Dict[str, Any] = {
            "success": False,
            "injected_count": 0,
            "missing_before": sorted(missing_chars),
            "missing_after": [],
            "tbl_updates": {},
            "sha256_before": "",
            "sha256_after": "",
            "error": "",
        }

        # --- Validate font_regions ---
        if not self._font_regions:
            result["error"] = (
                f"FONT_REGION_UNKNOWN: font_regions não definido para CRC32={self.crc32}. "
                f"Use o Font Editor para identificar o offset da fonte e adicione ao perfil."
            )
            result["missing_after"] = sorted(missing_chars)
            self._report = result
            return result

        # Use first (highest confidence) font region
        region = self._font_regions[0]
        offset_raw = region.get("offset", 0)
        if isinstance(offset_raw, str):
            font_offset = int(offset_raw, 16)
        else:
            font_offset = int(offset_raw)

        num_tiles = int(region.get("tiles", 256))
        if num_tiles < 128:
            num_tiles = 256  # Need enough space for accent tiles (0xC0+)

        bpp = int(region.get("bpp", 1))
        bytes_per_tile = 8 * bpp
        region_size = num_tiles * bytes_per_tile

        # SHA-256 before
        result["sha256_before"] = _sha256_region(self.rom_data, font_offset, region_size)

        # --- Load font map ---
        font_map = FontMap(self.rom_data, font_offset, bpp=bpp, num_tiles=num_tiles)

        # --- Determine ascii_base_offset ---
        # Profile may specify it explicitly; otherwise infer from encoding.
        # For "ascii" encoding: tiles indexed by ASCII value → base_offset = 0x20
        #   (tile[0x20]=space, tile[0x41]='A')
        # For "tilemap" encoding: tiles indexed by TBL byte → base_offset = 0
        #   (tile[0x00]=space, tile[0x21]='A')
        ascii_base_offset = region.get("ascii_base_offset", None)
        if ascii_base_offset is None:
            encoding = (self._profile or {}).get("encoding", "ascii")
            if encoding in ("tilemap", "tbl"):
                ascii_base_offset = 0
            else:
                ascii_base_offset = 0x20  # Standard ASCII (most common)
        ascii_base_offset = int(ascii_base_offset)

        ink_color = 1 if bpp == 1 else 15

        target_chars: Set[str] = set()
        if missing_chars:
            target_chars.update(
                unicodedata.normalize("NFC", str(ch))
                for ch in missing_chars
                if isinstance(ch, str) and len(str(ch)) == 1
            )
        else:
            target_chars.update(PTBR_ACCENTED_CHARS.keys())

        # --- Geração 1: acentos sintéticos a partir dos glifos base ---
        slots_hint = self._extract_region_slots(region)
        base_target = set(ch for ch in target_chars if ch in PTBR_ACCENTED_CHARS)
        accents = generate_all_ptbr_accents(
            font_map,
            ascii_base_offset=ascii_base_offset,
            ink_color=ink_color,
            fallback_slots=slots_hint,
            target_chars=base_target if base_target else None,
        )

        used_tiles = set(tile for tile, _ in accents.values())
        generated_base_chars = set(accents.keys())

        # --- Geração 2: fallback por Verdana para chars restantes ---
        unresolved_chars = set(target_chars) - generated_base_chars
        verdana_chars: Set[str] = set()
        source_font = ""
        if unresolved_chars:
            verdana_accents, source_font = self._generate_verdana_glyphs(
                target_chars=unresolved_chars,
                font_map=font_map,
                region=region,
                used_tiles=used_tiles,
                ink_color=ink_color,
            )
            if verdana_accents:
                verdana_chars = set(verdana_accents.keys())
                accents.update(verdana_accents)

        if not accents:
            result["error"] = (
                "GLYPH_GENERATION_FAILED: Não foi possível gerar glifos (base/Verdana). "
                "Verifique base da fonte e slots livres no perfil."
            )
            result["missing_after"] = sorted(missing_chars)
            self._report = result
            return result

        # --- Apply to font map (patches ROM in-memory) ---
        tbl_tile_entries = apply_accents_to_fontmap(font_map, accents)

        # --- Update TBL with new mappings ---
        new_tbl_entries: Dict[int, str] = {}
        tbl_updates_display: Dict[str, str] = {}

        for tile_index, char in tbl_tile_entries.items():
            # In TBL format: byte_value = tile_index (for 1-byte encoding)
            byte_val = tile_index
            new_tbl_entries[byte_val] = char
            tbl_updates_display[char] = f"0x{byte_val:02X}"

        tbl.merge_entries(new_tbl_entries)

        # --- Check what's still missing ---
        still_missing: Set[str] = set()
        reverse = getattr(tbl, "reverse_map", {})
        for ch in missing_chars:
            if ch not in reverse:
                still_missing.add(ch)

        # SHA-256 after
        result["sha256_after"] = _sha256_region(self.rom_data, font_offset, region_size)

        injected_count = len(tbl_tile_entries)
        result["success"] = True
        result["injected_count"] = injected_count
        result["injected_from_base_count"] = int(len(generated_base_chars))
        result["injected_from_verdana_count"] = int(len(verdana_chars))
        result["source_font"] = source_font or ""
        result["injected_chars"] = sorted(list(generated_base_chars | verdana_chars))
        result["missing_after"] = sorted(still_missing)
        result["tbl_updates"] = tbl_updates_display
        result["error"] = ""

        self._report = result
        return result

    # ------------------------------------------------------------------
    # Step 3: report
    # ------------------------------------------------------------------

    def get_report(self) -> Dict[str, Any]:
        """Return injection report for proof/report output."""
        return dict(self._report) if self._report else {}

    def has_font_regions(self) -> bool:
        """Check if font_regions are defined for this CRC32."""
        return len(self._font_regions) > 0
