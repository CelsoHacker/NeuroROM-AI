# -*- coding: utf-8 -*-
"""
Relocation manager por arquitetura.

Suposicoes minimas:
1) Alocacao de espaco livre usa FreeSpaceAllocator existente.
2) Atualizacao de ponteiros prioriza busca rapida por padrao binario.
3) PointerScanner existente entra como fallback para deteccao automatica.
"""

from __future__ import annotations

import contextlib
import io
from typing import Any

try:
    from .console_memory_model import ConsoleMemoryModel
    from .free_space_allocator import FreeSpaceAllocator
    from .pointer_scanner import PointerScanner
except Exception:  # pragma: no cover
    from console_memory_model import ConsoleMemoryModel
    from free_space_allocator import FreeSpaceAllocator
    from pointer_scanner import PointerScanner


def _to_console_alias(console_type: str) -> str:
    raw = str(console_type or "").strip().upper()
    aliases = {
        "GENESIS": "MD",
        "MEGADRIVE": "MD",
        "MASTER_SYSTEM": "SMS",
    }
    return aliases.get(raw, raw)


class RelocationManager:
    def __init__(self, console_model: ConsoleMemoryModel):
        self.console_model = console_model

    def relocate(
        self,
        rom_data: bytearray,
        old_offset: int,
        new_bytes: bytes,
    ) -> dict[str, Any]:
        """
        - Procura espaco livre seguro
        - Valida via ConsoleMemoryModel
        - Atualiza ponteiros usando PointerScanner
        - Evita sobrescrever codigo
        """
        if not isinstance(rom_data, bytearray):
            raise TypeError("rom_data precisa ser bytearray")

        result: dict[str, Any] = {
            "relocated": False,
            "reason": "unknown",
            "old_offset": int(old_offset),
            "new_offset": None,
            "bytes_written": 0,
            "pointers_updated": 0,
            "in_bounds": False,
            "within_free_space": False,
        }
        if old_offset < 0 or not new_bytes:
            result["reason"] = "invalid_input"
            return result

        console = _to_console_alias(self.console_model.console_type)
        allocator = FreeSpaceAllocator(rom_data, console)
        alignment = max(1, int(getattr(self.console_model, "alignment", 1)))
        new_offset = allocator.allocate(
            size=len(new_bytes),
            alignment=alignment,
            item_uid=f"reloc_{old_offset:06X}",
        )
        if new_offset is None:
            result["reason"] = "no_free_space"
            return result

        if not self.console_model.validate_write(new_offset, len(new_bytes)):
            result["reason"] = "memory_constraint_violation"
            result["new_offset"] = int(new_offset)
            result["in_bounds"] = (new_offset + len(new_bytes)) <= len(rom_data)
            result["within_free_space"] = self._is_within_allocator_regions(new_offset, len(new_bytes), allocator)
            return result

        rom_data[new_offset : new_offset + len(new_bytes)] = new_bytes
        fill = int(allocator.profile.get("fill_byte", 0xFF)) & 0xFF
        clear_len = min(len(new_bytes), max(0, len(rom_data) - old_offset))
        if clear_len > 0:
            rom_data[old_offset : old_offset + clear_len] = bytes([fill]) * clear_len

        pointers_updated = self._update_pointers(rom_data, old_offset, new_offset)
        result.update(
            {
                "relocated": True,
                "reason": "ok",
                "new_offset": int(new_offset),
                "bytes_written": int(len(new_bytes)),
                "pointers_updated": int(pointers_updated),
                "in_bounds": (new_offset + len(new_bytes)) <= len(rom_data),
                "within_free_space": self._is_within_allocator_regions(new_offset, len(new_bytes), allocator),
            }
        )
        return result

    def _is_within_allocator_regions(self, offset: int, size: int, allocator: FreeSpaceAllocator) -> bool:
        end = int(offset) + int(size)
        for region in getattr(allocator, "regions", []):
            start = int(getattr(region, "start", -1))
            stop = int(getattr(region, "end", -1))
            if start <= offset and end <= stop:
                return True
        # Em caso de expansão, a região pode ter sido adicionada dinamicamente.
        if end <= len(getattr(allocator, "rom_data", b"")):
            return True
        return False

    def _update_pointers(self, rom_data: bytearray, old_offset: int, new_offset: int) -> int:
        refs = self._collect_pointer_refs_fast(rom_data, old_offset)
        if not refs:
            refs = self._collect_pointer_refs_scanner(rom_data, old_offset)

        updated = 0
        for ref in refs:
            ptr_off = int(ref["offset"])
            ptr_size = int(ref["size"])
            endian = str(ref["endianness"])
            value = self._new_pointer_value(new_offset, ptr_size)
            try:
                rom_data[ptr_off : ptr_off + ptr_size] = int(value).to_bytes(ptr_size, endian, signed=False)
                updated += 1
            except Exception:
                continue
        return updated

    def _collect_pointer_refs_fast(self, rom_data: bytearray, old_offset: int) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[tuple[int, int, str]] = set()
        endianness_modes = self._endianness_modes()

        for size in (2, 3, 4):
            candidates = self._candidate_pointer_values(old_offset, size)
            for endian in endianness_modes:
                for candidate in candidates:
                    try:
                        pattern = int(candidate).to_bytes(size, endian, signed=False)
                    except OverflowError:
                        continue
                    pos = bytes(rom_data).find(pattern)
                    while pos >= 0:
                        key = (pos, size, endian)
                        if key not in seen:
                            seen.add(key)
                            refs.append({"offset": pos, "size": size, "endianness": endian})
                        pos = bytes(rom_data).find(pattern, pos + 1)
        return refs

    def _collect_pointer_refs_scanner(self, rom_data: bytearray, old_offset: int) -> list[dict[str, Any]]:
        endianness_modes = self._endianness_modes()
        scanner = PointerScanner(bytes(rom_data))
        with contextlib.redirect_stdout(io.StringIO()):
            scanner.scan(pointer_sizes=[2, 3, 4], endianness_modes=endianness_modes)

        refs: list[dict[str, Any]] = []
        seen: set[tuple[int, int, str]] = set()
        for pointer in scanner.all_pointers:
            if int(pointer.target_offset) != int(old_offset):
                continue
            if float(pointer.confidence) < 0.3:
                continue
            key = (int(pointer.offset), int(pointer.size), str(pointer.endianness))
            if key in seen:
                continue
            seen.add(key)
            refs.append({"offset": key[0], "size": key[1], "endianness": key[2]})
        return refs

    def _candidate_pointer_values(self, offset: int, size: int) -> list[int]:
        console = _to_console_alias(self.console_model.console_type)
        values = {int(offset)}

        if size == 2:
            if console == "SNES":
                values.add(0x8000 | (offset & 0x7FFF))
            if console in {"NES", "SMS"}:
                values.add(0x8000 | (offset & 0x3FFF))
        elif size == 3 and console == "SNES":
            bank = (offset // 0x8000) & 0xFF
            addr = 0x8000 | (offset & 0x7FFF)
            values.add((bank << 16) | addr)
        return sorted(values)

    def _new_pointer_value(self, new_offset: int, size: int) -> int:
        console = _to_console_alias(self.console_model.console_type)
        if size == 2:
            if console == "SNES":
                return 0x8000 | (new_offset & 0x7FFF)
            if console in {"NES", "SMS"}:
                return 0x8000 | (new_offset & 0x3FFF)
        if size == 3 and console == "SNES":
            bank = (new_offset // 0x8000) & 0xFF
            addr = 0x8000 | (new_offset & 0x7FFF)
            return (bank << 16) | addr
        mask = (1 << (size * 8)) - 1
        return int(new_offset) & mask

    def _endianness_modes(self) -> list[str]:
        console = _to_console_alias(self.console_model.console_type)
        if console == "MD":
            return ["big", "little"]
        return ["little", "big"]
