# -*- coding: utf-8 -*-
"""
UNIVERSAL TRANSLATOR v1.0
=========================
Sistema HÍBRIDO de tradução de ROMs com arquitetura driver-based.

Princípio: NÃO apaga nada. Adiciona por cima do código existente.
- Quando tem ASCII → extrai ASCII (usa SMSProExtractor existente)
- Quando tem TBL   → extrai com tabela customizada
- Quando tem SJIS  → extrai com Shift-JIS
- Quando não sabe  → tenta ASCII, se falhar reporta e sugere TBL

Componentes:
- GameProfileDB: Database JSON de jogos (CRC32 → metadados)
- PlatformDriver: Base abstrata para consoles
- SMSDriver: Driver Master System (HÍBRIDO)
- NESDriver: Driver NES (placeholder)
- GenesisDriver: Driver Genesis (placeholder)
- UniversalTranslator: Orquestrador principal

Autor: NeuroROM AI
Data: 2026-02
"""

from __future__ import annotations

import os
import json
import zlib
import struct
import math
import re
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from collections import Counter
from datetime import datetime, timezone

# Importa extratores existentes (NÃO MODIFICA, SÓ USA)
from sms_pro_extractor import (
    SMSProExtractor, SMSExtractorConfig, SMSPointerExtractor,
    SMSTilemapExtractor, TBLAutoLearner, ExtractionResult as SMSExtractionResult,
    ExtractedItem, ExtractionMethod, PointerTableCandidate
)
from tbl_loader import TBLLoader
from nes_extractor_pro import parse_ines_header
from sega_extractor import SegaExtractor


# ============================================================================
# GAME PROFILE DATABASE
# ============================================================================

@dataclass
class GameProfile:
    """Profile de um jogo no database."""
    crc32: str
    console: str                              # SMS, NES, GENESIS, SNES, GG
    name: str = ""
    region: str = "unknown"                   # JP, US, EU, BR
    encoding: str = "auto"                    # auto, ascii, tbl, sjis, custom
    tbl_path: Optional[str] = None            # Caminho relativo para .tbl
    terminators: List[int] = field(default_factory=lambda: [0x00])
    bank_rule: str = "SLOT1_4000"
    pointer_tables: List[Dict] = field(default_factory=list)
    font_regions: List[Dict] = field(default_factory=list)
    text_regions: List[Dict] = field(default_factory=list)
    compression: Optional[str] = None         # None, rle, lzss
    notes: str = ""


class GameProfileDB:
    """
    Database extensível de profiles de jogos.
    Adicionar novo jogo = adicionar entrada no JSON.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).parent / "game_profiles_db.json"
        self.profiles: Dict[str, GameProfile] = {}
        self._load()

    def _load(self):
        """Carrega database do disco."""
        if not self.db_path.exists():
            return

        with open(self.db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for entry in data.get('games', []):
            try:
                clean = dict(entry)
                clean.pop("notes", None)
                clean["name"] = str(clean.get("crc32", "")).upper()
                profile = GameProfile(**clean)
                self.profiles[profile.crc32.upper()] = profile
            except TypeError:
                # Campo desconhecido, ignora
                continue

    def save(self):
        """Salva database no disco."""
        data = {
            'schema': 'game_profiles_db.v1',
            'version': '1.0.0',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'total_games': len(self.profiles),
            'games': []
        }

        for profile in sorted(self.profiles.values(), key=lambda p: p.name):
            entry = asdict(profile)
            entry.pop("name", None)
            entry.pop("notes", None)
            data['games'].append(entry)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profile(self, crc32: str) -> Optional[GameProfile]:
        """Busca profile por CRC32."""
        return self.profiles.get(crc32.upper())

    def add_profile(self, profile: GameProfile, save: bool = True):
        """Adiciona ou atualiza profile."""
        self.profiles[profile.crc32.upper()] = profile
        if save:
            self.save()

    def list_by_console(self, console: str) -> List[GameProfile]:
        """Lista jogos por console."""
        return [p for p in self.profiles.values()
                if p.console.upper() == console.upper()]

    def stats(self) -> Dict[str, int]:
        """Estatísticas do database."""
        by_console: Dict[str, int] = {}
        by_encoding: Dict[str, int] = {}
        for p in self.profiles.values():
            by_console[p.console] = by_console.get(p.console, 0) + 1
            by_encoding[p.encoding] = by_encoding.get(p.encoding, 0) + 1
        return {
            'total': len(self.profiles),
            'by_console': by_console,
            'by_encoding': by_encoding,
        }


# ============================================================================
# EXTRACTION RESULT (UNIVERSAL)
# ============================================================================

@dataclass
class UniversalExtractionItem:
    """Item extraído (formato universal, compatível com pipeline existente)."""
    id: int
    offset: int
    raw_bytes: bytes
    raw_hex: str
    text: str
    encoding: str                             # ascii, tbl, sjis, tile, raw
    max_len_bytes: int
    terminator: int = 0x00
    source: str = "POINTER"                   # POINTER, TILEMAP, ASCII_SCAN
    reinsertion_safe: bool = False
    pointer_table_offset: Optional[int] = None
    pointer_entry_offset: Optional[int] = None
    confidence: float = 0.0
    blocked_reason: Optional[str] = None


@dataclass
class UniversalExtractionResult:
    """Resultado de extração universal."""
    success: bool
    crc32: str
    console: str
    game_name: str
    encoding_used: str
    method: str
    items: List[UniversalExtractionItem]
    total_items: int = 0
    safe_items: int = 0
    pointer_tables_found: int = 0
    font_regions_found: int = 0
    error: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# PLATFORM DRIVER (ABSTRACT)
# ============================================================================

class PlatformDriver(ABC):
    """Base abstrata para drivers de console."""

    @property
    @abstractmethod
    def console_name(self) -> str:
        """Nome do console."""

    @abstractmethod
    def detect(self, rom_data: bytes) -> bool:
        """Detecta se a ROM é deste console."""

    @abstractmethod
    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        """Extrai texto da ROM."""


# ============================================================================
# HYBRID SMS POINTER EXTRACTOR
# ============================================================================

class HybridSMSPointerExtractor(SMSPointerExtractor):
    """
    Extrator de ponteiros SMS com validação HÍBRIDA.
    Herda do SMSPointerExtractor existente, override apenas _is_valid_text.

    Quando encoding='ascii' → usa validação ASCII original
    Quando encoding='tbl'   → aceita bytes que mapeiam pela TBL
    Quando encoding='sjis'  → aceita bytes válidos em Shift-JIS
    Quando encoding='any'   → aceita qualquer sequência não-trivial
    """

    def __init__(self, rom_data: bytes, config: SMSExtractorConfig,
                 encoding: str = 'ascii',
                 tbl: Optional[TBLLoader] = None):
        super().__init__(rom_data, config)
        self.encoding = encoding
        self.tbl = tbl

    def _is_valid_text(self, data: bytes) -> bool:
        """Override: validação baseada no encoding do jogo."""
        if not data or len(data) < self.config.min_text_length:
            return False

        if self.encoding == 'ascii':
            return super()._is_valid_text(data)
        elif self.encoding == 'tbl' and self.tbl:
            return self._is_valid_tbl_text(data)
        elif self.encoding == 'sjis':
            return self._is_valid_sjis_text(data)
        else:
            return self._is_valid_generic_text(data)

    def _is_valid_tbl_text(self, data: bytes) -> bool:
        """Valida se bytes decodificam corretamente pela TBL."""
        decoded = self.tbl.decode_bytes(data, max_length=256)
        if len(decoded) < 2:
            return False
        # Precisa ter variedade (não tudo igual)
        if len(set(decoded)) < 2:
            return False
        # Não pode ser só espaços/controles
        if decoded.strip() == '':
            return False
        return True

    def _is_valid_sjis_text(self, data: bytes) -> bool:
        """Valida se bytes são Shift-JIS válido."""
        try:
            text = data.decode('shift_jis', errors='strict')
            if len(text) < 2:
                return False
            # Deve ter caracteres visíveis
            visible = sum(1 for c in text if not c.isspace() and ord(c) > 0x20)
            return visible >= 1
        except (UnicodeDecodeError, ValueError):
            return False

    def _is_valid_generic_text(self, data: bytes) -> bool:
        """Validação genérica: aceita dados não-triviais."""
        if len(data) < 3:
            return False
        # Não pode ser todo zeros ou todo FFs
        if all(b == 0 for b in data) or all(b == 0xFF for b in data):
            return False
        # Precisa ter variedade mínima
        unique = len(set(data))
        if unique < 2:
            return False
        # Não pode ser sequência monotônica (0,1,2,3,4...)
        diffs = [data[i+1] - data[i] for i in range(len(data)-1)]
        if len(set(diffs)) == 1 and len(data) > 4:
            return False
        return True


# ============================================================================
# SMS DRIVER (HÍBRIDO)
# ============================================================================

class SMSDriver(PlatformDriver):
    """
    Driver para consoles SMS / GG (8-bit, Z80-based).

    Extração HÍBRIDA:
    1. Se profile tem TBL → carrega TBL, descobre ponteiros, decodifica
    2. Se profile tem SJIS → descobre ponteiros, decodifica SJIS
    3. Se profile tem ASCII → usa SMSProExtractor existente
    4. Se sem profile (auto) → tenta ASCII, se falhar reporta
    """

    SMS_HEADER_OFFSET = 0x7FF0
    SMS_MAGIC = b"TMR SEGA"  # SMS ROM header magic bytes

    @property
    def console_name(self) -> str:
        return "SMS"

    def detect(self, rom_data: bytes) -> bool:
        """Detecta ROM SMS/GG pelo header magic bytes."""
        if len(rom_data) < 0x8000:
            return False
        return rom_data[self.SMS_HEADER_OFFSET:self.SMS_HEADER_OFFSET + 8] == self.SMS_MAGIC

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        """Extração principal com dispatch por encoding."""

        encoding = profile.encoding if profile else 'auto'

        if encoding == 'tilemap' and profile and profile.tbl_path:
            return self._extract_tilemap(rom_path, rom_data, crc32, profile)
        elif encoding == 'tbl' and profile and profile.tbl_path:
            return self._extract_with_tbl(rom_path, rom_data, crc32, profile)
        elif encoding == 'sjis':
            return self._extract_with_sjis(rom_path, rom_data, crc32, profile)
        elif encoding == 'ascii':
            return self._extract_with_ascii(rom_path, rom_data, crc32, profile)
        else:
            return self._extract_auto(rom_path, rom_data, crc32, profile)

    # ------------------------------------------------------------------
    # EXTRACTION: TILEMAP (2-byte VDP Name Table entries)
    # ------------------------------------------------------------------

    def _extract_tilemap(self, rom_path: str, rom_data: bytes, crc32: str,
                         profile: GameProfile) -> UniversalExtractionResult:
        """
        Extrai texto codificado como tilemap VDP (2 bytes por caractere).
        Cada caractere = [tile_low_byte] [attribute_byte].
        Usado por muitos jogos SMS que renderizam texto via Name Table.

        Modo 1: Se profile tem text_regions → extrai das regiões conhecidas
        Modo 2: Se não tem → escaneia ROM inteira por runs de pares válidos
        """
        tbl_path = self._resolve_tbl_path(rom_path, profile.tbl_path)
        if not tbl_path or not Path(tbl_path).exists():
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='SMS',
                game_name=profile.name, encoding_used='tilemap', method='TILEMAP',
                items=[], error=f"TBL file not found: {profile.tbl_path}"
            )

        tbl = TBLLoader(str(tbl_path))
        total_entries = len(tbl.char_map) + len(tbl.multi_byte_map)
        if total_entries == 0:
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='SMS',
                game_name=profile.name, encoding_used='tilemap', method='TILEMAP',
                items=[], error=f"TBL file empty: {tbl_path}"
            )

        items: List[UniversalExtractionItem] = []

        if profile.text_regions:
            # Modo 1: Regiões conhecidas do profile
            for region in profile.text_regions:
                region_start = region.get('start', 0)
                region_end = region.get('end', 0)
                label = region.get('label', '')

                if region_start <= 0 or region_end <= region_start:
                    continue
                if region_end > len(rom_data):
                    region_end = len(rom_data)

                region_items = self._scan_tilemap_region(
                    rom_data, tbl, region_start, region_end, label
                )
                items.extend(region_items)
        else:
            # Modo 2: Escaneia ROM inteira
            items = self._scan_tilemap_region(
                rom_data, tbl, 0, len(rom_data), 'full_scan'
            )

        # Renumera IDs
        for idx, item in enumerate(items):
            item.id = idx

        safe = sum(1 for i in items if i.reinsertion_safe)

        return UniversalExtractionResult(
            success=len(items) > 0,
            crc32=crc32, console='SMS',
            game_name=profile.name,
            encoding_used='tilemap', method='TILEMAP',
            items=items,
            total_items=len(items), safe_items=safe,
            pointer_tables_found=0,
            diagnostics={
                'tbl_entries': total_entries,
                'text_regions': len(profile.text_regions) if profile.text_regions else 0,
                'entry_size': f'{tbl.max_entry_len}-byte',
            }
        )

    def _scan_tilemap_region(self, rom_data: bytes, tbl: TBLLoader,
                              start: int, end: int,
                              label: str) -> List[UniversalExtractionItem]:
        """
        Escaneia uma região da ROM por sequências de pares tilemap decodificáveis.
        Retorna itens de texto encontrados.
        """
        items: List[UniversalExtractionItem] = []
        entry_len = tbl.max_entry_len  # Bytes per tilemap entry (2 for SMS VDP)
        i = start

        while i <= end - entry_len:
            # Tenta decodificar a partir desta posição
            seq_start = i
            text_chars = []
            j = i

            while j <= end - entry_len:
                seq = rom_data[j:j + entry_len]
                char = tbl.multi_byte_map.get(seq)
                if char is None and entry_len == 1:
                    char = tbl.char_map.get(rom_data[j])
                if char is not None:
                    text_chars.append(char)
                    j += entry_len
                else:
                    break

            text = ''.join(text_chars).strip()

            # Filtra: precisa ter conteúdo significativo
            alpha_count = sum(1 for c in text if c.isalpha())
            if alpha_count >= 3 and len(text) >= 3:
                raw_bytes = rom_data[seq_start:j]

                # Valida que não é padrão de tile/garbage
                is_safe = self._validate_tilemap_text(text)

                items.append(UniversalExtractionItem(
                    id=len(items),
                    offset=seq_start,
                    raw_bytes=raw_bytes,
                    raw_hex=raw_bytes.hex().upper(),
                    text=text,
                    encoding='tilemap',
                    max_len_bytes=len(raw_bytes),
                    terminator=0x00,
                    source=f'TILEMAP_{label}',
                    reinsertion_safe=is_safe,
                    confidence=0.9 if is_safe else 0.3,
                    blocked_reason=None if is_safe else 'TILEMAP_LOW_QUALITY',
                ))
                i = j  # Avança para depois do texto
            else:
                i += entry_len  # Avança 1 entrada

        return items

    def _validate_tilemap_text(self, text: str) -> bool:
        """Valida se texto extraído de tilemap é texto real de jogo."""
        if not text or len(text) < 3:
            return False

        # Precisa ter letras
        alpha = sum(1 for c in text if c.isalpha())
        if alpha < 3:
            return False

        # Rejeita padrões de tile
        if self._is_tile_pattern(text):
            return False

        # Precisa ter variedade de caracteres (mínimo absoluto, não ratio)
        clean = text.replace(' ', '')
        if len(clean) > 0:
            unique_count = len(set(clean))
            if unique_count < 4:
                return False

        # Texto com palavras reais tende a ter espaços ou ser > 4 chars
        # Fragmentos muito curtos sem espaço são suspeitos
        if len(text) < 4 and ' ' not in text:
            return False

        return True

    # ------------------------------------------------------------------
    # EXTRACTION: TBL
    # ------------------------------------------------------------------

    def _extract_with_tbl(self, rom_path: str, rom_data: bytes, crc32: str,
                          profile: GameProfile) -> UniversalExtractionResult:
        """Extrai texto usando tabela TBL customizada."""
        # Resolve caminho da TBL (relativo ao diretório da ROM ou absoluto)
        tbl_path = self._resolve_tbl_path(rom_path, profile.tbl_path)
        if not tbl_path or not Path(tbl_path).exists():
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='SMS',
                game_name=profile.name, encoding_used='tbl', method='TBL',
                items=[], error=f"TBL file not found: {profile.tbl_path}"
            )

        tbl = TBLLoader(str(tbl_path))
        if not tbl.char_map:
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='SMS',
                game_name=profile.name, encoding_used='tbl', method='TBL',
                items=[], error=f"TBL file empty or invalid: {tbl_path}"
            )

        config = SMSExtractorConfig()
        config.candidate_terminators = tuple(profile.terminators) if profile.terminators else (0x00,)

        # Usa pointer extractor HÍBRIDO (aceita bytes não-ASCII)
        pointer_ext = HybridSMSPointerExtractor(
            rom_data, config, encoding='tbl', tbl=tbl
        )

        # Descobre tabelas de ponteiros
        if profile.pointer_tables:
            tables = self._build_tables_from_profile(
                profile, pointer_ext, rom_data, config
            )
        else:
            tables = pointer_ext.discover_pointer_tables()

        # Extrai itens (com deduplicação por offset)
        items = []
        seen_offsets: Set[int] = set()
        for table in tables:
            for idx, (ptr_val, resolved) in enumerate(
                zip(table.pointer_values, table.resolved_offsets)
            ):
                if resolved in seen_offsets:
                    continue
                seen_offsets.add(resolved)

                raw = self._read_until_terminator(
                    rom_data, resolved, profile.terminators
                )
                if not raw or len(raw) < 2:
                    continue

                decoded = tbl.decode_bytes(raw, max_length=256)
                if not decoded or len(decoded) < 1:
                    continue

                is_safe = self._validate_decoded_text(decoded)

                items.append(UniversalExtractionItem(
                    id=len(items),
                    offset=resolved,
                    raw_bytes=raw,
                    raw_hex=raw.hex().upper(),
                    text=decoded,
                    encoding='tbl',
                    max_len_bytes=len(raw),
                    terminator=table.terminator,
                    source='POINTER',
                    reinsertion_safe=is_safe,
                    pointer_table_offset=table.table_offset,
                    pointer_entry_offset=table.table_offset + idx * 2,
                    confidence=table.confidence,
                    blocked_reason=None if is_safe else 'TBL_LOW_QUALITY',
                ))

        safe = sum(1 for i in items if i.reinsertion_safe)
        return UniversalExtractionResult(
            success=len(items) > 0,
            crc32=crc32, console='SMS',
            game_name=profile.name,
            encoding_used='tbl', method='TBL',
            items=items,
            total_items=len(items), safe_items=safe,
            pointer_tables_found=len(tables),
        )

    # ------------------------------------------------------------------
    # EXTRACTION: SJIS
    # ------------------------------------------------------------------

    def _extract_with_sjis(self, rom_path: str, rom_data: bytes, crc32: str,
                           profile: Optional[GameProfile]) -> UniversalExtractionResult:
        """Extrai texto Shift-JIS."""
        game_name = profile.name if profile else 'Unknown'
        config = SMSExtractorConfig()

        if profile and profile.terminators:
            config.candidate_terminators = tuple(profile.terminators)

        # Pointer extractor híbrido com validação SJIS
        pointer_ext = HybridSMSPointerExtractor(
            rom_data, config, encoding='sjis'
        )
        tables = pointer_ext.discover_pointer_tables()

        items = []
        terminators_set = set(profile.terminators) if profile and profile.terminators else {0x00}

        for table in tables:
            for idx, (ptr_val, resolved) in enumerate(
                zip(table.pointer_values, table.resolved_offsets)
            ):
                raw = self._read_until_terminator(
                    rom_data, resolved, list(terminators_set)
                )
                if not raw or len(raw) < 2:
                    continue

                try:
                    decoded = raw.decode('shift_jis', errors='replace')
                except (UnicodeDecodeError, ValueError):
                    continue

                if not decoded or len(decoded) < 1:
                    continue

                # Verifica se tem replacement characters demais
                replacements = decoded.count('\ufffd')
                is_safe = replacements == 0 and len(decoded) >= 2

                items.append(UniversalExtractionItem(
                    id=len(items),
                    offset=resolved,
                    raw_bytes=raw,
                    raw_hex=raw.hex().upper(),
                    text=decoded,
                    encoding='sjis',
                    max_len_bytes=len(raw),
                    terminator=table.terminator,
                    source='POINTER',
                    reinsertion_safe=is_safe,
                    pointer_table_offset=table.table_offset,
                    pointer_entry_offset=table.table_offset + idx * 2,
                    confidence=table.confidence,
                    blocked_reason=None if is_safe else 'SJIS_DECODE_ERROR',
                ))

        safe = sum(1 for i in items if i.reinsertion_safe)
        return UniversalExtractionResult(
            success=len(items) > 0,
            crc32=crc32, console='SMS',
            game_name=game_name,
            encoding_used='sjis', method='SJIS',
            items=items,
            total_items=len(items), safe_items=safe,
            pointer_tables_found=len(tables),
        )

    # ------------------------------------------------------------------
    # EXTRACTION: ASCII (usa extrator existente)
    # ------------------------------------------------------------------

    def _extract_with_ascii(self, rom_path: str, rom_data: bytes, crc32: str,
                            profile: Optional[GameProfile]) -> UniversalExtractionResult:
        """Extrai texto ASCII usando SMSProExtractor EXISTENTE."""
        game_name = profile.name if profile else 'Unknown'

        try:
            extractor = SMSProExtractor(rom_path)
            result = extractor.extract()
        except Exception as e:
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='SMS',
                game_name=game_name, encoding_used='ascii', method='ASCII',
                items=[], error=str(e)
            )

        # Converte resultado existente para formato universal
        items = []
        for item in extractor.items:
            is_safe = item.is_decoded and extractor._is_safe_item(item)
            items.append(UniversalExtractionItem(
                id=item.id,
                offset=item.file_offset,
                raw_bytes=item.raw_bytes,
                raw_hex=item.raw_hex,
                text=item.decoded_text,
                encoding='ascii' if item.is_decoded else 'raw',
                max_len_bytes=len(item.raw_bytes),
                terminator=item.terminator,
                source=item.method.value if hasattr(item.method, 'value') else str(item.method),
                reinsertion_safe=is_safe,
                pointer_table_offset=item.pointer_table_offset,
                pointer_entry_offset=(
                    item.pointer_table_offset + item.pointer_index * 2
                    if item.pointer_table_offset is not None and item.pointer_index is not None
                    else None
                ),
                confidence=item.confidence,
                blocked_reason=None if is_safe else 'NOT_PLAUSIBLE_TEXT_SMS',
            ))

        safe = sum(1 for i in items if i.reinsertion_safe)
        return UniversalExtractionResult(
            success=result.success,
            crc32=crc32, console='SMS',
            game_name=game_name,
            encoding_used='ascii', method='ASCII',
            items=items,
            total_items=len(items), safe_items=safe,
            pointer_tables_found=result.pointer_tables_found,
            error=result.error_message,
            diagnostics=result.diagnostics,
        )

    # ------------------------------------------------------------------
    # EXTRACTION: AUTO (híbrido)
    # ------------------------------------------------------------------

    def _extract_auto(self, rom_path: str, rom_data: bytes, crc32: str,
                      profile: Optional[GameProfile]) -> UniversalExtractionResult:
        """
        Detecção automática HÍBRIDA:
        1. Tenta ASCII (extrator existente)
        2. Se ASCII funcionar (safe_ratio >= 10%) → usa resultado
        3. Se falhar → tenta com validação genérica
        4. Reporta resultado com diagnóstico
        """
        game_name = profile.name if profile else 'Unknown'

        # PASSO 1: Tenta ASCII
        ascii_result = self._extract_with_ascii(rom_path, rom_data, crc32, profile)

        # Verifica se ASCII produziu resultados reais (não padrões de tile)
        ascii_real_safe = 0
        for item in ascii_result.items:
            if item.reinsertion_safe and not self._is_tile_pattern(item.text):
                ascii_real_safe += 1

        # Se ASCII tem boa cobertura COM texto real → retorna direto
        if ascii_result.success and ascii_real_safe >= 5:
            ascii_ratio = ascii_real_safe / max(1, ascii_result.total_items)
            if ascii_ratio >= 0.20:
                ascii_result.method = 'AUTO_ASCII'
                return ascii_result

        # PASSO 2: ASCII insuficiente → tenta extração genérica
        # (ponteiros com validação relaxada)
        config = SMSExtractorConfig()
        config.min_pointer_confidence = 0.50  # mais permissivo

        pointer_ext = HybridSMSPointerExtractor(
            rom_data, config, encoding='any'
        )
        tables = pointer_ext.discover_pointer_tables()

        generic_items = []
        for table in tables:
            for idx, (ptr_val, resolved) in enumerate(
                zip(table.pointer_values, table.resolved_offsets)
            ):
                raw = self._read_until_terminator(rom_data, resolved, [0x00])
                if not raw or len(raw) < 3:
                    continue

                # Tenta decodificar como ASCII
                try:
                    text = raw.decode('ascii')
                    enc = 'ascii'
                    is_safe = self._validate_decoded_text(text)
                except (UnicodeDecodeError, ValueError):
                    # Não é ASCII → mantém como raw hex para futura TBL
                    text = ''.join(f'{{{b:02X}}}' for b in raw)
                    enc = 'raw'
                    is_safe = False

                generic_items.append(UniversalExtractionItem(
                    id=len(generic_items),
                    offset=resolved,
                    raw_bytes=raw,
                    raw_hex=raw.hex().upper(),
                    text=text,
                    encoding=enc,
                    max_len_bytes=len(raw),
                    terminator=table.terminator,
                    source='POINTER',
                    reinsertion_safe=is_safe,
                    pointer_table_offset=table.table_offset,
                    pointer_entry_offset=table.table_offset + idx * 2,
                    confidence=table.confidence,
                    blocked_reason=None if is_safe else 'NEEDS_TBL',
                ))

        # Combina: itens safe do ASCII + itens do genérico
        combined = []
        seen_offsets: Set[int] = set()

        # Primeiro: itens safe do ASCII (filtra padrões de tile)
        for item in ascii_result.items:
            if item.reinsertion_safe and item.offset not in seen_offsets:
                if self._is_tile_pattern(item.text):
                    item.reinsertion_safe = False
                    item.blocked_reason = 'TILE_PATTERN'
                combined.append(item)
                seen_offsets.add(item.offset)

        # Depois: itens genéricos que não duplicam
        for item in generic_items:
            if item.offset not in seen_offsets:
                item.id = len(combined)
                combined.append(item)
                seen_offsets.add(item.offset)

        safe = sum(1 for i in combined if i.reinsertion_safe)
        needs_tbl = sum(1 for i in combined if i.blocked_reason == 'NEEDS_TBL')

        # Detecta font regions
        tilemap_ext = SMSTilemapExtractor(rom_data, config)
        fonts = tilemap_ext.detect_font_tiles()

        return UniversalExtractionResult(
            success=len(combined) > 0,
            crc32=crc32, console='SMS',
            game_name=game_name,
            encoding_used='auto', method='AUTO_HYBRID',
            items=combined,
            total_items=len(combined), safe_items=safe,
            pointer_tables_found=len(tables),
            font_regions_found=len(fonts),
            diagnostics={
                'ascii_items': ascii_result.total_items,
                'ascii_safe': ascii_result.safe_items,
                'generic_items': len(generic_items),
                'needs_tbl_count': needs_tbl,
                'font_candidates': [
                    {'offset': f"0x{f['offset']:06X}", 'score': f['score']}
                    for f in fonts[:5]
                ],
                'recommendation': (
                    'ROM needs custom TBL for full extraction. '
                    'Add tbl_path to game_profiles_db.json.'
                    if needs_tbl > safe
                    else 'ASCII extraction working.'
                ),
            }
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _read_until_terminator(self, rom_data: bytes, offset: int,
                               terminators: List[int],
                               max_len: int = 256) -> Optional[bytes]:
        """Lê bytes até encontrar terminador."""
        if offset < 0 or offset >= len(rom_data):
            return None

        result = bytearray()
        term_set = set(terminators)

        for i in range(offset, min(offset + max_len, len(rom_data))):
            b = rom_data[i]
            if b in term_set:
                break
            result.append(b)

        return bytes(result) if result else None

    def _validate_decoded_text(self, text: str) -> bool:
        """Valida se texto decodificado parece texto real de jogo."""
        if not text or len(text) < 2:
            return False
        # Precisa ter letras
        if not any(c.isalpha() for c in text):
            return False
        # Não pode ser tudo repetido
        if len(set(text)) < max(2, len(text) * 0.2):
            return False
        # Não pode ter tokens {XX} demais (sinal de raw não-decodificado)
        if text.count('{') > len(text) * 0.3:
            return False
        # Rejeita padrões de tile/font (AAAAAA, ABCABC, ABCDEFG...)
        if self._is_tile_pattern(text):
            return False
        return True

    def _is_tile_pattern(self, text: str) -> bool:
        """Detecta padrões de tile/font que não são texto real."""
        clean = text.replace(' ', '')
        if len(clean) < 4:
            return False

        # Padrão 1: Sequências alfabéticas (ABCDEF, abcdef, ZYXWVU)
        alpha_only = ''.join(c for c in clean if c.isalpha())
        if len(alpha_only) >= 4:
            diffs = [ord(alpha_only[i+1]) - ord(alpha_only[i])
                     for i in range(len(alpha_only) - 1)]
            if diffs:
                # Sequência consecutiva (A,B,C,D = diffs [1,1,1])
                consecutive = sum(1 for d in diffs if d == 1 or d == -1)
                if consecutive >= len(diffs) * 0.6 and len(diffs) >= 3:
                    return True

        # Padrão 2: Muito poucos caracteres únicos vs comprimento
        # (AAABBBCCC ou ABABABAB)
        # Para textos longos, o ratio naturalmente cai (26 letras / 300 chars = 0.087)
        # Então checamos contagem absoluta: < 4 únicos = provável padrão
        unique_count = len(set(clean))
        if unique_count < 4 and len(clean) > 6:
            return True

        # Padrão 3: Repetição de substring curta (ABCABC, AEAE)
        for sub_len in range(2, min(5, len(clean) // 2 + 1)):
            sub = clean[:sub_len]
            repeated = sub * (len(clean) // len(sub) + 1)
            if repeated[:len(clean)] == clean:
                return True

        return False

    def _resolve_tbl_path(self, rom_path: str, tbl_path: str) -> Optional[str]:
        """Resolve caminho da TBL (absoluto ou relativo à ROM)."""
        if not tbl_path:
            return None

        # Se absoluto, usa direto
        p = Path(tbl_path)
        if p.is_absolute() and p.exists():
            return str(p)

        # Relativo ao diretório da ROM
        rom_dir = Path(rom_path).parent
        candidate = rom_dir / tbl_path
        if candidate.exists():
            return str(candidate)

        # Relativo ao diretório do projeto
        project_dir = Path(__file__).parent.parent
        candidate = project_dir / tbl_path
        if candidate.exists():
            return str(candidate)

        return None

    def _build_tables_from_profile(self, profile: GameProfile,
                                    pointer_ext: HybridSMSPointerExtractor,
                                    rom_data: bytes,
                                    config: SMSExtractorConfig) -> List[PointerTableCandidate]:
        """Constrói tabelas de ponteiros a partir do profile (skip discovery)."""
        tables = []
        for pt in profile.pointer_tables:
            offset = pt.get('offset', 0)
            count = pt.get('count', 0)
            bank_rule = pt.get('bank_rule', profile.bank_rule)
            terminator = profile.terminators[0] if profile.terminators else 0x00

            if offset <= 0 or count <= 0:
                continue

            # Lê ponteiros diretamente
            ptr_values = []
            resolved_offsets = []
            rule_func = pointer_ext.BANK_RULES.get(bank_rule)
            if not rule_func:
                continue

            for i in range(count):
                ptr_off = offset + i * 2
                if ptr_off + 2 > len(rom_data):
                    break
                ptr_val = int.from_bytes(rom_data[ptr_off:ptr_off + 2], 'little')

                # Tenta resolver
                best = None
                num_banks = max(1, (len(rom_data) + 0x3FFF) // 0x4000)
                for bank in range(min(8, num_banks)):
                    resolved = rule_func(ptr_val, bank)
                    if resolved is not None and 0 <= resolved < len(rom_data):
                        best = resolved
                        break

                if best is not None:
                    ptr_values.append(ptr_val)
                    resolved_offsets.append(best)

            if ptr_values:
                tables.append(PointerTableCandidate(
                    table_offset=offset,
                    entry_count=len(ptr_values),
                    bank_rule=bank_rule,
                    terminator=terminator,
                    pointer_values=ptr_values,
                    resolved_offsets=resolved_offsets,
                    confidence=pt.get('confidence', 0.5),
                    valid_text_count=len(ptr_values),
                ))

        return tables


# ============================================================================
# HELPERS ASCII HEURÍSTICO (NES/GENESIS/SNES/GBA/N64/PS1)
# ============================================================================

_ASCII_SYMBOLS = set("!@#$%^&*()_+-=[]{}|;:'\",.<>?/\\`~")


def _is_ascii_printable(byte: int) -> bool:
    return 0x20 <= byte <= 0x7E


def _scan_ascii_runs(
    rom_data: bytes,
    *,
    start: int = 0,
    end: Optional[int] = None,
    min_len: int = 4,
    max_run_len: int = 240,
) -> List[Tuple[int, bytes, str, int]]:
    """Escaneia sequências ASCII contínuas em uma janela da ROM."""
    if end is None or end > len(rom_data):
        end = len(rom_data)
    start = max(0, start)
    end = max(start, end)

    runs: List[Tuple[int, bytes, str, int]] = []
    run_start: Optional[int] = None
    current = bytearray()

    def flush() -> None:
        nonlocal run_start, current
        if run_start is None or len(current) < min_len:
            run_start = None
            current = bytearray()
            return

        raw = bytes(current)
        text = raw.decode("ascii", errors="ignore").strip()
        if len(text) < min_len:
            run_start = None
            current = bytearray()
            return

        end_off = run_start + len(raw)
        terminator = rom_data[end_off] if end_off < len(rom_data) else 0x00
        runs.append((run_start, raw, text, terminator))
        run_start = None
        current = bytearray()

    for off in range(start, end):
        byte = rom_data[off]
        if _is_ascii_printable(byte):
            if run_start is None:
                run_start = off
                current = bytearray([byte])
                continue

            if len(current) < max_run_len:
                current.append(byte)
                continue

            # Bloco muito longo: fecha e começa outro para não explodir max_len.
            flush()
            run_start = off
            current = bytearray([byte])
            continue

        flush()

    flush()
    return runs


def _ascii_text_confidence(raw: bytes, text: str) -> float:
    """Pontuação simples [0..1] para priorizar texto humano visível."""
    if not raw:
        return 0.0

    printable = sum(1 for b in raw if _is_ascii_printable(b))
    printable_ratio = printable / max(1, len(raw))
    letters = sum(1 for c in text if c.isalpha())
    letter_ratio = letters / max(1, len(text))
    vowels = sum(1 for c in text if c in "aeiouAEIOU")
    vowel_ratio = vowels / max(1, letters) if letters else 0.0
    unique_ratio = len(set(text.replace(" ", ""))) / max(1, len(text.replace(" ", "")))

    score = (
        0.45 * printable_ratio
        + 0.25 * letter_ratio
        + 0.15 * vowel_ratio
        + 0.15 * min(1.0, unique_ratio * 4.0)
    )

    symbol_ratio = sum(1 for c in text if c in _ASCII_SYMBOLS) / max(1, len(text))
    if symbol_ratio > 0.45:
        score -= 0.20

    if len(text) >= 6 and letters > 0 and vowels == 0:
        score -= 0.20

    if len(text) >= 8 and len(set(text)) <= 2:
        score -= 0.25

    return max(0.0, min(1.0, score))


def _looks_like_game_text(text: str, *, min_len: int = 3) -> bool:
    """Filtro conservador para reduzir lixo ASCII."""
    t = (text or "").strip()
    if len(t) < min_len:
        return False

    letters = sum(1 for c in t if c.isalpha())
    if letters < 2:
        return False

    if len(t) >= 6 and sum(1 for c in t if c in "aeiouAEIOU") == 0:
        return False

    symbol_ratio = sum(1 for c in t if c in _ASCII_SYMBOLS) / max(1, len(t))
    if symbol_ratio > 0.45:
        return False

    t_low = t.lower()
    alpha = "abcdefghijklmnopqrstuvwxyz"
    for i in range(len(alpha) - 4):
        if alpha[i:i + 5] in t_low:
            return False
    if "01234" in t or "12345" in t or "23456" in t:
        return False

    if re.fullmatch(r"[0-9A-Fa-f]{6,}", t):
        return False

    return True


def _build_items_from_runs(
    runs: List[Tuple[int, bytes, str, int]],
    *,
    source: str,
    min_confidence: float,
    max_items: int = 12000,
    dedupe_by_text: bool = True,
) -> List[UniversalExtractionItem]:
    """Converte runs ASCII para itens universais."""
    items: List[UniversalExtractionItem] = []
    seen_text: Set[str] = set()

    for offset, raw, text, terminator in sorted(runs, key=lambda r: r[0]):
        normalized = text.strip()
        if not _looks_like_game_text(normalized):
            continue
        if dedupe_by_text and normalized in seen_text:
            continue

        confidence = _ascii_text_confidence(raw, normalized)
        safe = confidence >= min_confidence
        blocked_reason = None if safe else "LOW_CONFIDENCE"
        items.append(UniversalExtractionItem(
            id=len(items),
            offset=offset,
            raw_bytes=raw,
            raw_hex=raw.hex().upper(),
            text=normalized,
            encoding='ascii',
            max_len_bytes=len(raw),
            terminator=int(terminator),
            source=source,
            reinsertion_safe=safe,
            confidence=confidence,
            blocked_reason=blocked_reason,
        ))
        seen_text.add(normalized)

        if len(items) >= max_items:
            break

    return items


def _extract_ascii_window(
    *,
    rom_data: bytes,
    crc32: str,
    console: str,
    game_name: str,
    method: str,
    source: str,
    scan_start: int = 0,
    scan_end: Optional[int] = None,
    min_len: int = 4,
    min_confidence: float = 0.80,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> UniversalExtractionResult:
    """Executa extração ASCII em janela fixa e retorna formato universal."""
    runs = _scan_ascii_runs(
        rom_data,
        start=scan_start,
        end=scan_end,
        min_len=min_len,
        max_run_len=240,
    )
    items = _build_items_from_runs(
        runs,
        source=source,
        min_confidence=min_confidence,
        max_items=12000,
        dedupe_by_text=True,
    )
    safe = sum(1 for i in items if i.reinsertion_safe)
    success = len(items) > 0

    diag = dict(diagnostics or {})
    diag.update({
        "scan_start": int(scan_start),
        "scan_end": int(scan_end if scan_end is not None else len(rom_data)),
        "ascii_runs_found": int(len(runs)),
    })

    return UniversalExtractionResult(
        success=success,
        crc32=crc32,
        console=console,
        game_name=game_name,
        encoding_used='ascii',
        method=method,
        items=items,
        total_items=len(items),
        safe_items=safe,
        diagnostics=diag,
        error=None if success else f"Nenhum texto ASCII plausível encontrado para {console}.",
    )


# ============================================================================
# NES DRIVER (iNES PRG-ROM)
# ============================================================================

class NESDriver(PlatformDriver):
    """Driver NES com extração ASCII em PRG-ROM (iNES)."""

    NES_MAGIC = b"NES\x1a"

    @property
    def console_name(self) -> str:
        return "NES"

    def detect(self, rom_data: bytes) -> bool:
        return len(rom_data) >= 4 and rom_data[:4] == self.NES_MAGIC

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        try:
            hdr = parse_ines_header(rom_data)
        except Exception as exc:
            return UniversalExtractionResult(
                success=False, crc32=crc32, console='NES',
                game_name=profile.name if profile else f"NES_{crc32}",
                encoding_used='ascii', method='NES_PRG_ASCII',
                items=[],
                error=f"Falha ao ler header iNES: {exc}"
            )

        start = int(hdr.get("header_size", 16)) + int(hdr.get("trainer_size", 0))
        end = min(len(rom_data), start + int(hdr.get("prg_size", 0)))

        result = _extract_ascii_window(
            rom_data=rom_data,
            crc32=crc32,
            console='NES',
            game_name=profile.name if profile else f"NES_{crc32}",
            method='NES_PRG_ASCII',
            source='NES_PRG_ASCII_SCAN',
            scan_start=start,
            scan_end=end,
            min_len=4,
            min_confidence=0.80,
            diagnostics={
                "prg_16k": int(hdr.get("prg_16k", 0)),
                "chr_8k": int(hdr.get("chr_8k", 0)),
                "mapper": int(hdr.get("mapper", 0)),
                "has_trainer": bool(hdr.get("has_trainer", False)),
                "prg_window_size": int(max(0, end - start)),
            },
        )
        return result


# ============================================================================
# GENESIS DRIVER (Mega Drive) + fallback ASCII
# ============================================================================

class GenesisDriver(PlatformDriver):
    """Driver Genesis/Mega Drive com SegaExtractor + fallback heurístico."""

    @property
    def console_name(self) -> str:
        return "GENESIS"

    def detect(self, rom_data: bytes) -> bool:
        if len(rom_data) < 0x110:
            return False
        return b"SEGA" in rom_data[0x100:0x110]

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        diagnostics: Dict[str, Any] = {}
        items: List[UniversalExtractionItem] = []
        method = "GENESIS_ASCII_SCAN"

        try:
            extractor = SegaExtractor(rom_path)
            rows = extractor.extract_texts(min_length=4)
            diagnostics["sega_extractor_rows"] = int(len(rows))

            runs: List[Tuple[int, bytes, str, int]] = []
            for row in rows:
                offset = int(row.get("offset", 0))
                if offset < 0 or offset >= len(rom_data):
                    continue

                end = offset
                while end < len(rom_data) and _is_ascii_printable(rom_data[end]) and (end - offset) < 240:
                    end += 1

                raw = bytes(rom_data[offset:end])
                if not raw:
                    text_raw = str(row.get("text", "") or "").encode("ascii", errors="ignore")
                    raw = bytes(text_raw)
                text = str(row.get("text", "") or "").strip()
                if not text and raw:
                    text = raw.decode("ascii", errors="ignore").strip()
                if not text:
                    continue

                terminator = rom_data[end] if end < len(rom_data) else 0x00
                runs.append((offset, raw, text, terminator))

            items = _build_items_from_runs(
                runs,
                source='GENESIS_SEGA_EXTRACTOR',
                min_confidence=0.82,
                max_items=12000,
                dedupe_by_text=True,
            )
            method = "GENESIS_SEGA_EXTRACTOR"
        except Exception as exc:
            diagnostics["sega_extractor_error"] = str(exc)

        if not items:
            fallback = _extract_ascii_window(
                rom_data=rom_data,
                crc32=crc32,
                console='GENESIS',
                game_name=profile.name if profile else f"GENESIS_{crc32}",
                method='GENESIS_ASCII_SCAN',
                source='GENESIS_ASCII_SCAN',
                scan_start=0,
                scan_end=len(rom_data),
                min_len=4,
                min_confidence=0.82,
                diagnostics={"fallback_used": True},
            )
            if diagnostics:
                fallback.diagnostics.update(diagnostics)
            return fallback

        safe = sum(1 for i in items if i.reinsertion_safe)
        return UniversalExtractionResult(
            success=True,
            crc32=crc32,
            console='GENESIS',
            game_name=profile.name if profile else f"GENESIS_{crc32}",
            encoding_used='ascii',
            method=method,
            items=items,
            total_items=len(items),
            safe_items=safe,
            diagnostics=diagnostics,
        )


# ============================================================================
# DRIVERS HEURÍSTICOS (SNES / GBA / N64 / PS1)
# ============================================================================

class SNESDriver(PlatformDriver):
    """Driver SNES heurístico ASCII (fallback genérico)."""

    @property
    def console_name(self) -> str:
        return "SNES"

    def detect(self, rom_data: bytes) -> bool:
        if len(rom_data) < 0x8000:
            return False
        for base in (0x7FC0, 0xFFC0):
            if base + 0x20 >= len(rom_data):
                continue
            map_mode = rom_data[base + 0x15]
            if map_mode in {0x20, 0x21, 0x30, 0x31, 0x32, 0x35}:
                title = rom_data[base:base + 21]
                printable = sum(1 for b in title if 0x20 <= b <= 0x7E)
                if printable < 8:
                    continue

                # Checksum/complemento no header SNES tende a somar 0xFFFF.
                checksum_complement = rom_data[base + 0x1C] | (rom_data[base + 0x1D] << 8)
                checksum = rom_data[base + 0x1E] | (rom_data[base + 0x1F] << 8)
                if ((checksum + checksum_complement) & 0xFFFF) == 0xFFFF:
                    return True
        return False

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        has_copier_header = (len(rom_data) % 0x8000) == 512
        start = 512 if has_copier_header else 0
        return _extract_ascii_window(
            rom_data=rom_data,
            crc32=crc32,
            console='SNES',
            game_name=profile.name if profile else f"SNES_{crc32}",
            method='SNES_ASCII_HEURISTIC',
            source='SNES_ASCII_SCAN',
            scan_start=start,
            scan_end=len(rom_data),
            min_len=4,
            min_confidence=0.80,
            diagnostics={"has_copier_header": bool(has_copier_header)},
        )


class GBADriver(PlatformDriver):
    """Driver GBA heurístico ASCII (fallback genérico)."""

    @property
    def console_name(self) -> str:
        return "GBA"

    def detect(self, rom_data: bytes) -> bool:
        return len(rom_data) >= 0xC0 and rom_data[0xB2] == 0x96

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        return _extract_ascii_window(
            rom_data=rom_data,
            crc32=crc32,
            console='GBA',
            game_name=profile.name if profile else f"GBA_{crc32}",
            method='GBA_ASCII_HEURISTIC',
            source='GBA_ASCII_SCAN',
            scan_start=0xC0,
            scan_end=len(rom_data),
            min_len=4,
            min_confidence=0.80,
            diagnostics={"header_skipped_bytes": 0xC0},
        )


class N64Driver(PlatformDriver):
    """Driver Nintendo 64 heurístico ASCII (fallback genérico)."""

    _MAGICS = {
        b"\x80\x37\x12\x40",  # big-endian
        b"\x37\x80\x40\x12",  # byte-swapped
        b"\x40\x12\x37\x80",  # little-endian
        b"\x12\x40\x80\x37",  # word-swapped
    }

    @property
    def console_name(self) -> str:
        return "N64"

    def detect(self, rom_data: bytes) -> bool:
        return len(rom_data) >= 4 and rom_data[:4] in self._MAGICS

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        return _extract_ascii_window(
            rom_data=rom_data,
            crc32=crc32,
            console='N64',
            game_name=profile.name if profile else f"N64_{crc32}",
            method='N64_ASCII_HEURISTIC',
            source='N64_ASCII_SCAN',
            scan_start=0,
            scan_end=len(rom_data),
            min_len=4,
            min_confidence=0.82,
            diagnostics={},
        )


class PS1Driver(PlatformDriver):
    """Driver PlayStation 1 heurístico ASCII (scan parcial controlado)."""

    @property
    def console_name(self) -> str:
        return "PS1"

    def detect(self, rom_data: bytes) -> bool:
        if len(rom_data) >= 0x8006 and rom_data[0x8001:0x8006] == b"CD001":
            return True
        probe = rom_data[: min(len(rom_data), 4 * 1024 * 1024)]
        probe_upper = probe.upper()
        if b"CD001" in probe and (b"PLAYSTATION" in probe_upper or b"SYSTEM.CNF" in probe_upper):
            return True
        return b"PLAYSTATION" in probe_upper

    def extract(self, rom_path: str, rom_data: bytes, crc32: str,
                profile: Optional[GameProfile] = None) -> UniversalExtractionResult:
        scan_limit = min(len(rom_data), 64 * 1024 * 1024)
        method = 'PS1_ASCII_HEURISTIC'
        if scan_limit < len(rom_data):
            method = 'PS1_ASCII_HEURISTIC_PARTIAL_SCAN'

        return _extract_ascii_window(
            rom_data=rom_data,
            crc32=crc32,
            console='PS1',
            game_name=profile.name if profile else f"PS1_{crc32}",
            method=method,
            source='PS1_ASCII_SCAN',
            scan_start=0,
            scan_end=scan_limit,
            min_len=5,
            min_confidence=0.84,
            diagnostics={
                "scan_limit_bytes": int(scan_limit),
                "scan_truncated": bool(scan_limit < len(rom_data)),
            },
        )


# ============================================================================
# GAME GEAR DRIVER (HERDA SMS)
# ============================================================================

class GameGearDriver(SMSDriver):
    """Driver para Game Gear - herda tudo do SMS."""

    @property
    def console_name(self) -> str:
        return "GG"

    def detect(self, rom_data: bytes) -> bool:
        # GG usa o mesmo header do SMS
        return super().detect(rom_data)


# ============================================================================
# UNIVERSAL TRANSLATOR (ORQUESTRADOR)
# ============================================================================

class UniversalTranslator:
    """
    Orquestrador universal de tradução de ROMs.

    Uso:
        translator = UniversalTranslator()
        result = translator.process_rom("castle_of_illusion.sms")
        translator.export(result, "./output/")
    """

    def __init__(self, game_db_path: Optional[str] = None):
        self.game_db = GameProfileDB(game_db_path)
        self.drivers: Dict[str, PlatformDriver] = {
            'SMS': SMSDriver(),
            'GG': GameGearDriver(),
            'NES': NESDriver(),
            'GENESIS': GenesisDriver(),
            'SNES': SNESDriver(),
            'GBA': GBADriver(),
            'N64': N64Driver(),
            'PS1': PS1Driver(),
        }

    def detect_console(self, rom_path: str) -> str:
        """Detecta console com prioridade por extensão (quando não ambígua)."""
        rom_data = Path(rom_path).read_bytes()
        ext = Path(rom_path).suffix.lower()

        # Extensões não ambíguas: força o driver esperado.
        ext_direct_map = {
            '.sms': 'SMS', '.gg': 'GG',
            '.nes': 'NES',
            '.md': 'GENESIS', '.gen': 'GENESIS', '.smd': 'GENESIS',
            '.sfc': 'SNES', '.smc': 'SNES',
            '.gba': 'GBA',
            '.z64': 'N64', '.n64': 'N64', '.v64': 'N64',
            '.iso': 'PS1', '.cue': 'PS1', '.chd': 'PS1', '.pbp': 'PS1',
            '.ccd': 'PS1', '.img': 'PS1', '.mds': 'PS1', '.psx': 'PS1',
        }
        forced = ext_direct_map.get(ext)
        if forced in self.drivers:
            return forced

        # Extensão ambígua (.bin): tenta assinaturas específicas.
        if ext == '.bin':
            if self.drivers['PS1'].detect(rom_data):
                return 'PS1'
            if self.drivers['GENESIS'].detect(rom_data):
                return 'GENESIS'
            return 'GENESIS'

        # Header detection
        for name, driver in self.drivers.items():
            if driver.detect(rom_data):
                return name

        return 'UNKNOWN'

    def process_rom(self, rom_path: str) -> UniversalExtractionResult:
        """
        Processa uma ROM: detecta console, busca profile, extrai texto.

        Este é o ponto de entrada principal.
        """
        rom_path = str(Path(rom_path).resolve())
        rom_data = Path(rom_path).read_bytes()
        crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"
        console = self.detect_console(rom_path)

        # Busca profile
        profile = self.game_db.get_profile(crc32)

        if profile:
            # Usa console do profile apenas quando ele confirma a detecção atual
            # ou quando a detecção ficou UNKNOWN.
            profile_console = str(profile.console or "").upper()
            if profile_console in self.drivers:
                if console == 'UNKNOWN' or profile_console == console:
                    console = profile_console

        if console not in self.drivers:
            return UniversalExtractionResult(
                success=False, crc32=crc32, console=console,
                game_name=profile.name if profile else 'Unknown',
                encoding_used='n/a', method='N/A',
                items=[],
                error=f'Console "{console}" not supported. Available: {list(self.drivers.keys())}'
            )

        driver = self.drivers[console]
        result = driver.extract(rom_path, rom_data, crc32, profile)

        # Auto-registro: se jogo não está no DB, registra
        if not profile and result.total_items > 0:
            self._auto_register(crc32, rom_path, console, result)

        return result

    def _auto_register(self, crc32: str, rom_path: str, console: str,
                       result: UniversalExtractionResult):
        """Auto-registra jogo no database após primeira extração."""
        profile = GameProfile(
            crc32=crc32,
            name=f"{console}_{crc32}_auto",
            console=console,
            encoding='auto',
            notes=f'Auto-registered. Method: {result.method}. '
                  f'Items: {result.total_items}, Safe: {result.safe_items}',
        )
        self.game_db.add_profile(profile)

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export(self, result: UniversalExtractionResult, output_dir: str,
               formats: Tuple[str, ...] = ('jsonl', 'txt', 'report')):
        """Exporta resultado em múltiplos formatos."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        crc = result.crc32

        paths = {}
        if 'jsonl' in formats:
            paths['jsonl'] = self._export_jsonl(result, out / f"{crc}_pure_text.jsonl")
        if 'txt' in formats:
            paths['txt'] = self._export_txt(result, out / f"{crc}_extracted.txt")
        if 'mapping' in formats or 'jsonl' in formats:
            paths['mapping'] = self._export_mapping(result, out / f"{crc}_reinsertion_mapping.json")
        if 'report' in formats:
            paths['report'] = self._export_report(result, out / f"{crc}_report.txt")
        if 'script' in formats:
            paths['script'] = self._export_script(result, out / f"{crc}_script.txt")

        return paths

    def _export_jsonl(self, result: UniversalExtractionResult, path: Path) -> str:
        """Exporta JSONL (compatível com pipeline existente)."""
        with open(path, 'w', encoding='utf-8') as f:
            for item in result.items:
                entry = {
                    'id': item.id,
                    'offset': f'0x{item.offset:06X}',
                    'text_src': item.text,
                    'max_len_bytes': item.max_len_bytes,
                    'encoding': item.encoding,
                    'source': item.source,
                    'reinsertion_safe': item.reinsertion_safe,
                    'raw_hex': item.raw_hex,
                    'terminator': item.terminator,
                    'confidence': round(item.confidence, 3),
                }
                if item.pointer_table_offset is not None:
                    entry['pointer_table_offset'] = item.pointer_table_offset
                if item.pointer_entry_offset is not None:
                    entry['pointer_entry_offset'] = item.pointer_entry_offset
                if item.blocked_reason:
                    entry['blocked_reason'] = item.blocked_reason
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return str(path)

    def _export_mapping(self, result: UniversalExtractionResult, path: Path) -> str:
        """Exporta mapping de reinserção (compatível com pipeline existente)."""
        mapping = {
            'schema': 'universal_translator.mapping.v1',
            'file_crc32': result.crc32,
            'console': result.console,
            'encoding': result.encoding_used,
            'method': result.method,
            'statistics': {
                'total_items': result.total_items,
                'safe_items': result.safe_items,
                'coverage': result.safe_items / max(1, result.total_items),
                'pointer_tables_found': result.pointer_tables_found,
            },
            'text_blocks': []
        }

        for item in result.items:
            block = {
                'id': item.id,
                'offset': item.offset,
                'max_length': item.max_len_bytes,
                'terminator': item.terminator,
                'source': item.source,
                'encoding': item.encoding,
                'pointer_table_offset': item.pointer_table_offset,
                'pointer_entry_offset': item.pointer_entry_offset,
                'reinsertion_safe': item.reinsertion_safe,
            }
            if item.blocked_reason:
                block['blocked_reason'] = item.blocked_reason
            mapping['text_blocks'].append(block)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        return str(path)

    def _export_txt(self, result: UniversalExtractionResult, path: Path) -> str:
        """Exporta texto puro (para tradução manual)."""
        with open(path, 'w', encoding='utf-8') as f:
            for item in result.items:
                if item.reinsertion_safe:
                    f.write(f"#{item.id}|0x{item.offset:06X}|{item.max_len_bytes}\n")
                    f.write(f"{item.text}\n\n")
        return str(path)

    def _export_script(self, result: UniversalExtractionResult, path: Path) -> str:
        """Exporta no formato script (Atlas-compatible)."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"; Script for {result.game_name}\n")
            f.write(f"; CRC32: {result.crc32}\n")
            f.write(f"; Console: {result.console}\n")
            f.write(f"; Encoding: {result.encoding_used}\n")
            f.write(f"; Total: {result.total_items} | Safe: {result.safe_items}\n")
            f.write(f"; Generated by UniversalTranslator v1.0\n\n")

            for item in result.items:
                if item.reinsertion_safe:
                    f.write(f"#W16(${item.offset:06X})\n")
                    f.write(f"{item.text}\n")
                    f.write(f"#END()\n\n")
        return str(path)

    def _export_report(self, result: UniversalExtractionResult, path: Path) -> str:
        """Exporta relatório legível."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("UNIVERSAL TRANSLATOR - EXTRACTION REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"GAME: {result.game_name}\n")
            f.write(f"CRC32: {result.crc32}\n")
            f.write(f"CONSOLE: {result.console}\n")
            f.write(f"ENCODING: {result.encoding_used}\n")
            f.write(f"METHOD: {result.method}\n")
            f.write(f"SUCCESS: {result.success}\n\n")

            f.write("-" * 40 + "\n")
            f.write("STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"TOTAL_ITEMS: {result.total_items}\n")
            f.write(f"SAFE_ITEMS: {result.safe_items}\n")
            coverage = result.safe_items / max(1, result.total_items)
            f.write(f"COVERAGE: {coverage:.1%}\n")
            f.write(f"POINTER_TABLES: {result.pointer_tables_found}\n")
            f.write(f"FONT_REGIONS: {result.font_regions_found}\n\n")

            if result.error:
                f.write("-" * 40 + "\n")
                f.write("ERROR\n")
                f.write("-" * 40 + "\n")
                f.write(f"{result.error}\n\n")

            if result.diagnostics:
                f.write("-" * 40 + "\n")
                f.write("DIAGNOSTICS\n")
                f.write("-" * 40 + "\n")
                for k, v in result.diagnostics.items():
                    f.write(f"{k}: {v}\n")
                f.write("\n")

            f.write("-" * 40 + "\n")
            f.write("ITEMS PREVIEW (top 20)\n")
            f.write("-" * 40 + "\n")
            for item in result.items[:20]:
                safe = "[SAFE]" if item.reinsertion_safe else "[----]"
                text = item.text[:60] + "..." if len(item.text) > 60 else item.text
                f.write(f"{safe} #{item.id:03d} @0x{item.offset:06X} [{item.encoding}] {text}\n")

            if len(result.items) > 20:
                f.write(f"... +{len(result.items) - 20} more items\n")

        return str(path)


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI para Universal Translator."""
    import sys

    print("=" * 60)
    print("UNIVERSAL TRANSLATOR v1.0 - Hybrid ROM Text Extraction")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nUso:")
        print("  python universal_translator.py <rom_file> [output_dir]")
        print("\nExemplos:")
        print("  python universal_translator.py castle.sms")
        print("  python universal_translator.py game.nes ./output/")
        print("\nO sistema detecta automaticamente o console e encoding.")
        print("Para melhor resultado, configure game_profiles_db.json")
        print("com TBL customizado para o jogo.")
        sys.exit(0)

    rom_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(Path(rom_path).parent)

    try:
        translator = UniversalTranslator()

        print(f"\nROM: {Path(rom_path).name}")
        console = translator.detect_console(rom_path)
        print(f"Console: {console}")

        rom_data = Path(rom_path).read_bytes()
        crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"
        print(f"CRC32: {crc32}")

        profile = translator.game_db.get_profile(crc32)
        if profile:
            print(f"Profile: {profile.name} [{profile.encoding}]")
        else:
            print("Profile: Not in database (auto-detect)")

        print(f"\nExtracting...")
        result = translator.process_rom(rom_path)

        print(f"\nResult:")
        print(f"  Method: {result.method}")
        print(f"  Encoding: {result.encoding_used}")
        print(f"  Total items: {result.total_items}")
        print(f"  Safe items: {result.safe_items}")
        coverage = result.safe_items / max(1, result.total_items)
        print(f"  Coverage: {coverage:.1%}")

        if result.success:
            paths = translator.export(result, output_dir)
            print(f"\nExported:")
            for fmt, path in paths.items():
                print(f"  {fmt}: {path}")
        else:
            print(f"\nError: {result.error}")

        if result.diagnostics:
            print(f"\nDiagnostics:")
            for k, v in result.diagnostics.items():
                print(f"  {k}: {v}")

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
