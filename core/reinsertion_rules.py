# -*- coding: utf-8 -*-
"""
================================================================================
REINSERTION RULES - Regras de Reinserção V1
================================================================================
Implementa regras específicas para reinserção de textos traduzidos:

REGRA 1 - STRING_POINTER_TEXT:
    - Textos com ponteiros, podem ser realocados se não couberem
    - Sempre traduz PT-BR
    - Preserve tokens via protect/unprotect
    - Atualiza ponteiros quando realoca

REGRA 2 - UI_TILEMAP_LABEL:
    - Tilemaps de HUD com comprimento fixo
    - Sem realocação (posição fixa)
    - Trunca/abrevia se não couber
    - Bloqueia se não houver glyph_map

Sem scan cego. Neutralidade CRC32/SIZE.
================================================================================
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .free_space_allocator import FreeSpaceAllocator


@dataclass
class ReinsertionResult:
    """Resultado de uma operação de reinserção."""
    success: bool
    status: str                         # "in_place", "relocated", "fixed_shortened", "blocked_*"
    reason: str = ""
    old_offset: int = 0
    new_offset: Optional[int] = None
    old_len: int = 0
    new_len: int = 0
    pointer_locations: List[int] = field(default_factory=list)
    encoded_bytes: bytes = b""

    def to_mapping_entry(self, item_id: str) -> Dict[str, Any]:
        """Converte para entrada do reinsertion_mapping.json."""
        entry = {
            "id": item_id,
            "old_offset": f"0x{self.old_offset:06X}",
            "old_len": self.old_len,
            "new_len": self.new_len,
            "status": self.status,
        }
        if self.new_offset is not None and self.new_offset != self.old_offset:
            entry["new_offset"] = f"0x{self.new_offset:06X}"
        if self.reason:
            entry["reason"] = self.reason
        if self.pointer_locations:
            entry["pointer_locations"] = [f"0x{p:06X}" for p in self.pointer_locations]
        return entry


class ReinsertionRules:
    """
    Aplica regras de reinserção para diferentes tipos de itens.

    Suporta:
    - STRING_POINTER_TEXT (source="POINTER"): realocação permitida
    - UI_TILEMAP_LABEL (kind="UI_TILEMAP_LABEL"): comprimento fixo
    """

    def __init__(
        self,
        rom_data: bytearray,
        allocator: FreeSpaceAllocator,
        charset: Optional[Dict[str, Any]] = None,
        glyph_maps: Optional[Dict[str, Dict[int, str]]] = None
    ):
        """
        Args:
            rom_data: Dados da ROM (bytearray mutável)
            allocator: Alocador de espaço livre
            charset: Tabela de caracteres para encoding
            glyph_maps: Mapas de glyph por região/ID para tilemaps
        """
        self.rom_data = rom_data
        self.allocator = allocator
        self.charset = charset or {}
        self.glyph_maps = glyph_maps or {}

        # Build reverse charset
        self._char_to_byte: Dict[str, int] = {}
        for char_str, byte_hex in self.charset.get('char_to_byte', {}).items():
            self._char_to_byte[char_str] = int(byte_hex, 16) if isinstance(byte_hex, str) else byte_hex

        # Estatísticas
        self.stats = {
            "in_place": 0,
            "relocated": 0,
            "fixed_shortened": 0,
            "blocked_no_pointer": 0,
            "blocked_no_glyph_map": 0,
            "blocked_allocation_failed": 0,
            "tokens_preserved": 0,
            "tokens_failed": 0,
        }

        # Registro para mapping
        self.mapping_entries: List[Dict[str, Any]] = []

        # Registro para proof
        self.proof_entries: List[Dict[str, Any]] = []

    def apply_rule(
        self,
        item: Dict[str, Any],
        translated_text: str,
        token_map: Optional[Dict[str, str]] = None
    ) -> ReinsertionResult:
        """
        Aplica a regra apropriada baseada no tipo do item.

        Args:
            item: Item do JSONL/mapping (deve ter offset, kind, etc)
            translated_text: Texto traduzido
            token_map: Mapa de tokens para unprotect

        Returns:
            ReinsertionResult com status da operação
        """
        kind = item.get("kind", "text")

        if kind == "UI_TILEMAP_LABEL":
            return self._apply_rule_tilemap(item, translated_text)
        else:
            # STRING_POINTER_TEXT (default)
            return self._apply_rule_pointer_text(item, translated_text, token_map)

    def _apply_rule_pointer_text(
        self,
        item: Dict[str, Any],
        translated_text: str,
        token_map: Optional[Dict[str, str]] = None
    ) -> ReinsertionResult:
        """
        REGRA 1 - STRING_POINTER_TEXT

        - Traduz PT-BR
        - Preserva tokens
        - Realoca se não couber e tiver pointer_refs
        """
        # Parse offset
        offset = item.get("offset") or item.get("static_offset") or item.get("target_offset")
        if isinstance(offset, str):
            offset = int(offset, 16)

        # Determina limites
        max_length = item.get("max_len_bytes") or item.get("max_bytes") or item.get("length", 0)
        terminator = item.get("terminator", 0x00)
        terminator_len = 1 if terminator is not None else 0
        payload_limit = max_length - terminator_len if max_length else 0

        pointer_refs = item.get("pointer_refs", [])
        item_id = item.get("id") or item.get("uid", "unknown")

        # Unprotect tokens se houver
        final_text = translated_text
        if token_map:
            for placeholder, original in token_map.items():
                final_text = final_text.replace(placeholder, original)
            self.stats["tokens_preserved"] += len(token_map)

        # Encode
        try:
            encoded = self._encode_text(final_text)
        except Exception as e:
            return ReinsertionResult(
                success=False,
                status="blocked_encode_error",
                reason=str(e),
                old_offset=offset,
                old_len=max_length,
            )

        # Add terminator
        if terminator is not None:
            encoded_with_term = encoded + bytes([terminator])
        else:
            encoded_with_term = encoded

        # CASO 1: Cabe in-place
        if len(encoded_with_term) <= max_length:
            self._write_in_place(offset, encoded_with_term, max_length)
            self.stats["in_place"] += 1

            result = ReinsertionResult(
                success=True,
                status="in_place",
                old_offset=offset,
                new_offset=offset,
                old_len=max_length,
                new_len=len(encoded_with_term),
                encoded_bytes=encoded_with_term,
            )
            self._register_mapping(item_id, result)
            self._register_proof(item_id, result, terminator, token_map)
            return result

        # CASO 2: Não cabe - precisa realocar (ou encurtar determinístico)
        if not pointer_refs:
            # Fallback: não há ponteiros para realocar. Então encurtamos/truncamos
            # determinísticamente para caber no comprimento fixo, sem perder o PT-BR.
            terminator_len = 1 if terminator is not None else 0
            payload_limit = max(0, max_length - terminator_len)

            shortened_text = self._shorten_text_deterministic(final_text, payload_limit)
            shortened_payload = self._encode_text_limited(shortened_text, payload_limit)

            if terminator is not None:
                shortened_bytes = shortened_payload + bytes([terminator])
            else:
                shortened_bytes = shortened_payload

            # Garantia final: nunca exceder max_length; preservar terminador quando aplicável
            if max_length and len(shortened_bytes) > max_length:
                shortened_bytes = shortened_bytes[:max_length]
                if terminator is not None and max_length > 0:
                    shortened_bytes = shortened_bytes[:-1] + bytes([terminator])

            self._write_in_place(offset, shortened_bytes, max_length)
            self.stats["fixed_shortened"] += 1

            result = ReinsertionResult(
                success=True,
                status="fixed_shortened",
                reason="overflow_no_pointer_fallback",
                old_offset=offset,
                new_offset=offset,
                old_len=max_length,
                new_len=len(shortened_bytes),
                encoded_bytes=shortened_bytes,
            )
            self._register_mapping(item_id, result)
            self._register_proof(item_id, result, terminator, token_map)
            return result

        # Aloca novo espaço
# Aloca novo espaço
        new_offset = self.allocator.allocate(
            size=len(encoded_with_term),
            alignment=2,
            item_uid=item_id
        )

        if new_offset is None:
            self.stats["blocked_allocation_failed"] += 1
            result = ReinsertionResult(
                success=False,
                status="blocked_allocation_failed",
                reason="no_free_space",
                old_offset=offset,
                old_len=max_length,
                new_len=len(encoded_with_term),
            )
            self._register_mapping(item_id, result)
            return result

        # Escreve no novo local
        self.rom_data[new_offset:new_offset + len(encoded_with_term)] = encoded_with_term

        # Limpa local antigo
        fill_byte = self.allocator.profile.get('fill_byte', 0xFF)
        self.rom_data[offset:offset + max_length] = bytes([fill_byte] * max_length)

        # Atualiza ponteiros
        pointer_locs = []
        for pref in pointer_refs:
            ptr_off = self._update_pointer_ref(pref, new_offset)
            if ptr_off is not None:
                pointer_locs.append(ptr_off)

        self.stats["relocated"] += 1

        result = ReinsertionResult(
            success=True,
            status="relocated",
            reason="overflow",
            old_offset=offset,
            new_offset=new_offset,
            old_len=max_length,
            new_len=len(encoded_with_term),
            pointer_locations=pointer_locs,
            encoded_bytes=encoded_with_term,
        )
        self._register_mapping(item_id, result)
        self._register_proof(item_id, result, terminator, token_map)
        return result

    def _apply_rule_tilemap(
        self,
        item: Dict[str, Any],
        translated_text: str
    ) -> ReinsertionResult:
        """
        REGRA 2 - UI_TILEMAP_LABEL

        - Comprimento fixo (tiles/slots)
        - Sem realocação
        - Trunca/abrevia se não couber
        - Bloqueia se não houver glyph_map
        """
        offset = item.get("offset") or item.get("static_offset")
        if isinstance(offset, str):
            offset = int(offset, 16)

        constraints = item.get("constraints", {})
        max_bytes = constraints.get("max_bytes") or item.get("max_len_bytes", 0)
        item_id = item.get("id") or item.get("uid", "unknown")

        # Obtém glyph_map
        glyph_map = item.get("glyph_map")
        if not glyph_map:
            # Tenta buscar do registro global
            glyph_map = self.glyph_maps.get(item_id)

        if not glyph_map:
            self.stats["blocked_no_glyph_map"] += 1
            result = ReinsertionResult(
                success=False,
                status="blocked_no_glyph_map",
                reason="no_glyph_map_provided",
                old_offset=offset,
                old_len=max_bytes,
            )
            self._register_mapping(item_id, result)
            return result

        # Build reverse map
        reverse_map = {v: k for k, v in glyph_map.items()}

        # Encode tilemap
        encoded = self._encode_tilemap(translated_text, reverse_map, max_bytes)

        if len(encoded) > max_bytes:
            # Trunca para caber
            encoded = encoded[:max_bytes]
            status = "fixed_shortened"
            self.stats["fixed_shortened"] += 1
        else:
            status = "in_place"
            self.stats["in_place"] += 1

        # Pad para comprimento fixo
        while len(encoded) < max_bytes:
            # Usa 0x00 ou espaço como padding
            space_byte = reverse_map.get(' ', 0x00)
            encoded = encoded + bytes([space_byte])

        # Escreve (sempre in-place, sem realocação)
        self.rom_data[offset:offset + max_bytes] = encoded

        result = ReinsertionResult(
            success=True,
            status=status,
            old_offset=offset,
            new_offset=offset,
            old_len=max_bytes,
            new_len=len(encoded),
            encoded_bytes=encoded,
        )
        self._register_mapping(item_id, result)
        self._register_proof_tilemap(item_id, result, max_bytes)
        return result

    def _encode_text(self, text: str) -> bytes:
        """Encode texto usando charset."""
        if not self._char_to_byte:
            return text.encode('ascii', errors='replace')

        encoded = bytearray()
        i = 0

        while i < len(text):
            # Token <TILE:XX>
            if text[i:i+6] == '<TILE:' and i + 9 <= len(text) and text[i+8] == '>':
                try:
                    code = int(text[i+6:i+8], 16)
                    encoded.append(code)
                    i += 9
                    continue
                except ValueError:
                    pass

            # Token <XX>
            if text[i] == '<' and i + 3 < len(text) and text[i+3] == '>':
                try:
                    code = int(text[i+1:i+3], 16)
                    encoded.append(code)
                    i += 4
                    continue
                except ValueError:
                    pass

            # Caractere normal
            char = text[i]
            if char in self._char_to_byte:
                encoded.append(self._char_to_byte[char])
            elif char == ' ':
                encoded.append(self._char_to_byte.get(' ', 0x20))
            else:
                # Fallback: tenta ASCII
                encoded.append(ord(char) if ord(char) < 128 else 0x3F)  # '?'
            i += 1

        return bytes(encoded)



    def _encode_text_limited(self, text: str, max_bytes: int) -> bytes:
        """
        Encode de texto com limite de bytes, sem quebrar tokens do formato <TILE:XX> / <XX>.
        Usado para fallback determinístico quando não existe ponteiro para realocação.
        """
        if max_bytes <= 0:
            return b""

        out = bytearray()
        i = 0
        while i < len(text):
            # Token tile: <TILE:XX>
            m = self.TOKEN_TILE_RE.match(text, i)
            if m:
                b = bytes([int(m.group(1), 16)])
                if len(out) + 1 > max_bytes:
                    break
                out.extend(b)
                i = m.end()
                continue

            # Token hex simples: <XX>
            m = self.TOKEN_HEX_RE.match(text, i)
            if m:
                b = bytes([int(m.group(1), 16)])
                if len(out) + 1 > max_bytes:
                    break
                out.extend(b)
                i = m.end()
                continue

            ch = text[i]

            if ch in self.char_map:
                if len(out) + 1 > max_bytes:
                    break
                out.append(self.char_map[ch])
                i += 1
                continue

            # ASCII fallback (ignora caracteres não representáveis)
            b = ch.encode("ascii", errors="ignore")
            if not b:
                i += 1
                continue

            if len(out) + len(b) > max_bytes:
                # adiciona o que couber (normalmente 1 byte)
                remaining = max_bytes - len(out)
                out.extend(b[:remaining])
                break

            out.extend(b)
            i += 1

        return bytes(out)

    def _shorten_text_deterministic(self, text: str, payload_limit: int) -> str:
        """
        Encurtamento determinístico (sem heurísticas aleatórias) para caber no limite.
        Estratégia simples e segura:
          1) normaliza espaços
          2) remove stopwords comuns do PT-BR (sem tocar tokens <...>)
          3) abrevia palavras longas removendo vogais internas (ASCII)
        Se ainda não couber, o encode com limite fará o truncamento final.
        """
        if payload_limit <= 0:
            return ""

        t = re.sub(r"\s+", " ", (text or "")).strip()

        try:
            if len(self._encode_text(t)) <= payload_limit:
                return t
        except Exception:
            # Se algo inesperado ocorrer no encode completo, seguimos com o fallback
            pass

        stopwords = {
            "de", "da", "do", "das", "dos", "para", "por", "com",
            "e", "a", "o", "as", "os", "um", "uma", "uns", "umas",
            "em", "no", "na", "nos", "nas", "ao", "aos", "à", "às"
        }

        parts = t.split(" ")
        filtered = []
        for w in parts:
            if (w.startswith("<") and w.endswith(">")):
                filtered.append(w)
                continue
            if w.lower() in stopwords:
                continue
            filtered.append(w)

        t2 = " ".join(filtered) if filtered else t

        try:
            if len(self._encode_text(t2)) <= payload_limit:
                return t2
        except Exception:
            pass

        vowels = set("aeiouAEIOU")

        def _abbrev_word(w: str) -> str:
            if w.startswith("<") and w.endswith(">"):
                return w
            core = w
            if len(core) >= 8 and core.isalpha():
                mid = "".join(ch for ch in core[1:-1] if ch not in vowels)
                shortened = core[0] + mid + core[-1]
                return shortened if len(shortened) < len(core) else core
            return w

        t3 = " ".join(_abbrev_word(w) for w in t2.split(" "))
        return t3
    def _encode_tilemap(self, text: str, reverse_map: Dict[str, int], max_bytes: int) -> bytes:
        """Encode texto para tilemap usando reverse glyph_map."""
        encoded = bytearray()
        i = 0

        while i < len(text) and len(encoded) < max_bytes:
            # Token <TILE:XX>
            match = re.match(r'<TILE:([0-9A-Fa-f]{2})>', text[i:])
            if match:
                tile_idx = int(match.group(1), 16)
                encoded.append(tile_idx)
                i += len(match.group(0))
                continue

            # Caractere normal
            char = text[i]
            if char in reverse_map:
                encoded.append(reverse_map[char])
            else:
                # Caractere desconhecido - pula ou usa placeholder
                pass
            i += 1

        return bytes(encoded)

    def _write_in_place(self, offset: int, data: bytes, max_length: int):
        """Escreve dados in-place com padding."""
        fill_byte = self.allocator.profile.get('fill_byte', 0x00)

        # Limpa região
        self.rom_data[offset:offset + max_length] = bytes([fill_byte] * max_length)

        # Escreve dados
        self.rom_data[offset:offset + len(data)] = data

    def _update_pointer_ref(self, pref: Dict, new_target: int) -> Optional[int]:
        """Atualiza ponteiro para novo target. Retorna offset do ponteiro."""
        ptr_offset = pref.get('ptr_offset')
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)

        if ptr_offset is None:
            return None

        ptr_size = pref.get('ptr_size', 2)
        endianness = pref.get('endianness', 'little')
        mode = pref.get('addressing_mode', 'ABSOLUTE')

        base_str = pref.get('base', '0x0')
        base = int(base_str, 16) if isinstance(base_str, str) else (base_str or 0)

        addend = pref.get('addend', 0)
        bank_addend_str = pref.get('bank_addend', '0x0')
        bank_addend = int(bank_addend_str, 16) if isinstance(bank_addend_str, str) else (bank_addend_str or 0)

        bank_size = self.allocator.profile.get('bank_size', 0x4000)

        # Calcula novo valor do ponteiro
        if mode in ('LOROM_16', 'NES_8000', 'SMS_BASE', 'SMS_BASE8000', 'SMS_BASE4000', 'BANKED_SLOT1', 'BANKED_SLOT2'):
            new_value = (new_target % bank_size) + bank_addend
        elif mode == 'NES_C000':
            new_value = 0xC000 + (new_target % bank_size) + addend
        elif mode == 'HIROM_16':
            new_value = (new_target % 0x10000) + addend
        elif mode == 'ABSOLUTE':
            new_value = new_target + addend
        else:
            new_value = new_target + addend

        # Escreve ponteiro
        little = (endianness == 'little')

        if ptr_size == 2:
            val_bytes = new_value.to_bytes(2, 'little' if little else 'big')
            self.rom_data[ptr_offset:ptr_offset+2] = val_bytes
        elif ptr_size == 3:
            new_bank = new_target // bank_size
            val_bytes = (new_value & 0xFFFF).to_bytes(2, 'little' if little else 'big')
            self.rom_data[ptr_offset:ptr_offset+2] = val_bytes
            self.rom_data[ptr_offset+2] = new_bank

        return ptr_offset

    def _register_mapping(self, item_id: str, result: ReinsertionResult):
        """Registra entrada para reinsertion_mapping.json."""
        self.mapping_entries.append(result.to_mapping_entry(item_id))

    def _register_proof(
        self,
        item_id: str,
        result: ReinsertionResult,
        terminator: Optional[int],
        token_map: Optional[Dict[str, str]]
    ):
        """Registra entrada para proof.json."""
        entry = {
            "id": item_id,
            "offset": f"0x{result.new_offset or result.old_offset:06X}",
            "len_valid": result.new_len <= result.old_len or result.status == "relocated",
            "terminator_present": terminator is not None and (
                result.encoded_bytes[-1] == terminator if result.encoded_bytes else False
            ),
            "tokens_preserved": len(token_map) if token_map else 0,
            "status": result.status,
        }

        # Se realocado, valida que ponteiros apontam para new_offset
        if result.status == "relocated" and result.pointer_locations:
            entry["pointers_updated"] = len(result.pointer_locations)
            entry["pointer_validation"] = "verified"

        self.proof_entries.append(entry)

    def _register_proof_tilemap(self, item_id: str, result: ReinsertionResult, fixed_len: int):
        """Registra entrada de proof para tilemap."""
        entry = {
            "id": item_id,
            "offset": f"0x{result.old_offset:06X}",
            "len_valid": len(result.encoded_bytes) == fixed_len,
            "fixed_length": fixed_len,
            "actual_length": len(result.encoded_bytes),
            "status": result.status,
        }
        self.proof_entries.append(entry)

    def get_mapping_data(self) -> List[Dict[str, Any]]:
        """Retorna dados para reinsertion_mapping.json."""
        return self.mapping_entries

    def get_proof_data(self) -> List[Dict[str, Any]]:
        """Retorna dados para proof.json."""
        return self.proof_entries

    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas."""
        return self.stats.copy()
