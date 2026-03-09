# -*- coding: utf-8 -*-
"""retro8_bank_tools.py

Ferramentas utilitárias para injeção com realocação + repoint em ROMs 8-bit.

Objetivo: dar suporte a:
- Busca de espaço livre dentro de um bank (limite rígido)
- Expansão de ROM em múltiplos do bank_size
- Atualização de ponteiros 16-bit e ponteiros banked (bank + addr)
- Detecção heurística de 'bank tables' paralelas (1 byte por entrada)

Obs: Não tenta "entender" a engine do jogo.
Ela funciona por inferência a partir de:
- offsets extraídos
- padrões de pointer tables (endereços 0x8000..0xFFFF etc)
- valores de banks válidos (0..N-1)

V6.0 PRO (NeuroROM AI)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict


@dataclass
class PointerRef:
    """Uma referência de ponteiro encontrada na ROM."""
    ptr_offset: int                 # onde os bytes do ponteiro estão
    table_start: Optional[int]      # início provável da tabela (se detectado)
    index: Optional[int]            # índice dentro da tabela (se detectado)
    mode: str                       # ex: 'NES_8000', 'NES_C000', 'SMS_BASE8000'
    # Campos estendidos para realocacao automatica:
    ptr_size: int = 2               # tamanho do ponteiro (2, 3 ou 4 bytes)
    endianness: str = 'little'      # 'little' ou 'big'
    base: int = 0                   # base de enderecamento (ex: 0x8000 para NES)
    bank: Optional[int] = None      # banco atual (para sistemas banked)
    addend: int = 0                 # offset adicional (raro, mas suportado)
    bank_table_offset: Optional[int] = None  # offset da bank table paralela

    def to_dict(self) -> Dict:
        """Converte para dicionario (para JSON export)."""
        return {
            'ptr_offset': f"0x{self.ptr_offset:06X}",
            'ptr_size': self.ptr_size,
            'endianness': self.endianness,
            'addressing_mode': self.mode,
            'base': f"0x{self.base:04X}" if self.base else None,
            'bank': self.bank,
            'addend': self.addend,
            'table_start': f"0x{self.table_start:06X}" if self.table_start else None,
            'index': self.index,
            'bank_table_offset': f"0x{self.bank_table_offset:06X}" if self.bank_table_offset else None
        }


def _find_all(haystack: bytes, needle: bytes) -> List[int]:
    """Retorna todos os offsets onde needle ocorre em haystack (sem sobreposição)."""
    out: List[int] = []
    start = 0
    while True:
        i = haystack.find(needle, start)
        if i == -1:
            break
        out.append(i)
        start = i + 1
    return out


def find_free_space_in_range(
    rom: bytearray,
    start: int,
    end: int,
    required: int,
    patterns: Tuple[int, ...] = (0x00, 0xFF),
    alignment: int = 1,
    safety_slack: int = 1,
) -> Optional[int]:
    """Procura um bloco contínuo >= required dentro [start, end).

    - patterns: bytes considerados 'vazios'
    - alignment: alinha o offset retornado
    - safety_slack: margem para terminador (ex: +1 pro \x00)
    """
    if required <= 0:
        return None

    need = required + max(0, safety_slack)
    start = max(0, start)
    end = min(len(rom), end)
    if start >= end:
        return None

    for pad in patterns:
        run_start = None
        run_len = 0
        i = start
        while i < end:
            if rom[i] == pad:
                if run_start is None:
                    run_start = i
                    run_len = 1
                else:
                    run_len += 1

                if run_len >= need:
                    cand = run_start
                    if alignment > 1:
                        cand = (cand + alignment - 1) & ~(alignment - 1)
                    if cand + required <= run_start + run_len and cand + required <= end:
                        return cand
            else:
                run_start = None
                run_len = 0
            i += 1

    return None


def expand_rom_in_banks(
    rom: bytearray,
    bank_size: int,
    extra_bytes_needed: int,
    fill: int = 0xFF,
) -> Tuple[int, int]:
    """Expande ROM em múltiplos de bank_size para acomodar extra_bytes_needed.

    Retorna (old_size, new_size).
    """
    if bank_size <= 0:
        raise ValueError('bank_size inválido')

    old = len(rom)
    if extra_bytes_needed <= 0:
        return old, old

    # sempre adiciona pelo menos 1 bank se precisar de espaço
    banks_needed = (extra_bytes_needed + bank_size - 1) // bank_size
    rom.extend(bytes([fill]) * (banks_needed * bank_size))
    return old, len(rom)


def guess_pointer_table_bounds_16(
    rom: bytes,
    ptr_offset: int,
    little_endian: bool = True,
    valid_range: Tuple[int, int] = (0x8000, 0xFFFF),
) -> Tuple[int, int]:
    """Dado um offset de ponteiro 16-bit, tenta expandir para limites de uma tabela.

    Critério: valores consecutivos de ISC (2 bytes) dentro de valid_range.
    Retorna (table_start, table_end_exclusive).
    """
    step = 2

    def read16(off: int) -> int:
        b0 = rom[off]
        b1 = rom[off + 1]
        return (b0 | (b1 << 8)) if little_endian else (b1 | (b0 << 8))

    lo, hi = valid_range

    # anda pra trás
    s = ptr_offset
    while s - step >= 0:
        v = read16(s - step)
        if lo <= v <= hi:
            s -= step
        else:
            break

    # anda pra frente
    e = ptr_offset + step
    while e + 1 < len(rom):
        v = read16(e)
        if lo <= v <= hi:
            e += step
        else:
            break

    return s, e


def detect_parallel_bank_table(
    rom: bytes,
    table_start: int,
    entry_count: int,
    prg_bank_count: int,
    expected_bank_by_index: Optional[Dict[int, int]] = None,
    search_window: int = 0x2000,
) -> Optional[int]:
    """Procura uma bank table (1 byte/entrada) que alinhe com a pointer table.

    Heurística:
    - Varre candidatos perto de table_start (±search_window)
    - Avalia quantos bytes são banks válidos (0..prg_bank_count-1)
    - Se expected_bank_by_index fornecido, reforça match

    Retorna offset do início da bank table ou None.
    """
    if entry_count <= 0:
        return None

    lo = 0
    hi = max(0, prg_bank_count - 1)

    best_off = None
    best_score = 0.0

    start = max(0, table_start - search_window)
    end = min(len(rom) - entry_count, table_start + search_window)

    # tentativa: candidatos mais prováveis são próximos e alinhados
    for cand in range(start, end):
        block = rom[cand:cand + entry_count]
        if not block:
            continue

        valid = sum(1 for b in block if lo <= b <= hi)
        ratio = valid / entry_count
        if ratio < 0.85:
            continue

        # bônus por match com expected_bank_by_index
        bonus = 0.0
        if expected_bank_by_index:
            matches = 0
            for idx, eb in expected_bank_by_index.items():
                if 0 <= idx < entry_count and block[idx] == eb:
                    matches += 1
            bonus = (matches / max(1, len(expected_bank_by_index))) * 0.25

        # penaliza distância
        dist = abs(cand - table_start)
        dist_pen = min(0.25, dist / max(1, search_window) * 0.25)

        score = ratio + bonus - dist_pen
        if score > best_score:
            best_score = score
            best_off = cand

    return best_off


def patch_u16(rom: bytearray, off: int, value: int, little_endian: bool = True):
    value &= 0xFFFF
    if little_endian:
        rom[off] = value & 0xFF
        rom[off + 1] = (value >> 8) & 0xFF
    else:
        rom[off] = (value >> 8) & 0xFF
        rom[off + 1] = value & 0xFF


def find_pointer_refs_by_expected_u16(
    rom: bytes,
    expected_values: List[Tuple[int, str]],
    little_endian: bool = True,
) -> List[PointerRef]:
    """Busca ocorrências de qualquer u16 esperado e retorna refs.

    expected_values: [(u16_value, mode_str), ...]
    """
    refs: List[PointerRef] = []
    for val, mode in expected_values:
        b = val.to_bytes(2, 'little' if little_endian else 'big')
        for off in _find_all(rom, b):
            t0, t1 = guess_pointer_table_bounds_16(rom, off, little_endian=little_endian)
            idx = (off - t0) // 2 if t0 is not None else None
            refs.append(PointerRef(ptr_offset=off, table_start=t0, index=idx, mode=mode))
    return refs


# ---------------------------------------------------------------------------
# Compat aliases (V6 PRO integration)
# ---------------------------------------------------------------------------

def find_free_space_in_bank(rom: bytearray, bank_start: int, bank_size: int,
                           required_size: int, patterns=(0x00,0xFF), alignment: int = 1) -> int | None:
    """Alias: procura espaço livre dentro de um bank (range fixo)."""
    return find_free_space_in_range(rom, bank_start, bank_start + bank_size, required_size, patterns=patterns, alignment=alignment)


def detect_pointer_table_window_2byte(rom: bytes, ptr_offset: int, little_endian: bool = True):
    """Alias: detecta janela provável de tabela 2-byte envolvendo ptr_offset.

    Retorna (table_start, count) ou (None, None).
    """
    b = guess_pointer_table_bounds_16(rom, ptr_offset, little_endian=little_endian)
    if not b:
        return None, None
    start, end = b
    count = (end - start) // 2
    return start, count


def find_pointer_refs_by_expected_bytes(rom: bytes, expected: bytes) -> list[int]:
    """Alias: retorna offsets onde os bytes esperados ocorrem."""
    return _find_all(rom, expected)


def find_pointer_refs_by_expected_u16(rom: bytes, u16_value: int, little_endian: bool = True) -> list[int]:
    # Já existe com esse nome no arquivo, mas garantimos aqui caso seja importado por engano.
    return find_pointer_refs_by_expected_u16(rom, u16_value, little_endian=little_endian)


def expand_by_banks(current_size: int, extra_needed: int, bank_size: int) -> tuple[int, int]:
    """Calcula quantos banks de 'bank_size' precisam ser adicionados.

    Retorna (new_size_aligned, banks_added).
    """
    if bank_size <= 0:
        raise ValueError('bank_size invalido')
    if extra_needed <= 0:
        return current_size, 0
    new_size = ((current_size + extra_needed + bank_size - 1) // bank_size) * bank_size
    added = (new_size - current_size) // bank_size
    return new_size, added

    expected_value &= 0xFFFF
    b = (
        bytes([expected_value & 0xFF, (expected_value >> 8) & 0xFF])
        if little_endian
        else bytes([(expected_value >> 8) & 0xFF, expected_value & 0xFF])
    )
    offs = _find_all(rom, b)
    out: List[PointerRef] = []
    for off in offs:
        t0, t1 = guess_pointer_table_bounds_16(
            rom, off, little_endian=little_endian, valid_range=valid_range
        )
        idx = (off - t0) // 2 if t0 is not None else None
        out.append(PointerRef(ptr_offset=off, table_start=t0, index=idx, mode=mode))
    return out


def patch_banked_pointer3(
    rom: bytearray,
    ptr_offset: int,
    bank: int,
    addr16: int,
    layout: str = 'BANK_ADDR_LE',
) -> None:
    """Atualiza ponteiro 3 bytes (bank + addr16) ou (addr16 + bank).

    layout:
      - 'BANK_ADDR_LE': [bank][lo][hi]
      - 'ADDR_LE_BANK': [lo][hi][bank]
    """
    bank &= 0xFF
    addr16 &= 0xFFFF
    lo = addr16 & 0xFF
    hi = (addr16 >> 8) & 0xFF
    if layout == 'ADDR_LE_BANK':
        rom[ptr_offset:ptr_offset + 3] = bytes([lo, hi, bank])
    else:
        rom[ptr_offset:ptr_offset + 3] = bytes([bank, lo, hi])


def iter_banked_pointer3(
    rom: bytes,
    expected_bank: int,
    expected_addr16: int,
    layout: str = 'BANK_ADDR_LE',
    mode: str = 'BANKED3',
) -> List[PointerRef]:
    """Encontra ocorrências de ponteiro 3 bytes (bank + addr16)."""
    expected_bank &= 0xFF
    expected_addr16 &= 0xFFFF
    lo = expected_addr16 & 0xFF
    hi = (expected_addr16 >> 8) & 0xFF
    needle = (
        bytes([lo, hi, expected_bank])
        if layout == 'ADDR_LE_BANK'
        else bytes([expected_bank, lo, hi])
    )
    offs = _find_all(rom, needle)
    return [PointerRef(ptr_offset=o, table_start=None, index=None, mode=mode) for o in offs]


def detect_sms_pointer_base(
    rom: bytes,
    string_offsets: List[int],
    bank_size: int = 0x4000,
    bases: Tuple[int, ...] = (0x8000, 0x4000, 0x0000),
    little_endian: bool = True,
) -> int:
    """Tenta inferir base de endereçamento para ponteiros SMS (0x8000/0x4000/0x0000).

    Score: soma de ocorrências dos u16 esperados para uma amostra de offsets.
    """
    sample = string_offsets[: min(200, len(string_offsets))]
    best_base = bases[0]
    best_score = -1

    for base in bases:
        score = 0
        for off in sample:
            addr = (base + (off % bank_size)) & 0xFFFF
            b = (
                bytes([addr & 0xFF, (addr >> 8) & 0xFF])
                if little_endian
                else bytes([(addr >> 8) & 0xFF, addr & 0xFF])
            )
            score += rom.count(b)
        if score > best_score:
            best_score = score
            best_base = base

    return best_base

# ---------------------------------------------------------------------------
# Pointer patching & scanning helpers (NES/SMS)
# ---------------------------------------------------------------------------

def detect_pointer_table_window_16(rom: bytes, any_ptr_offset: int, little_endian: bool = True) -> tuple[int, int]:
    """Retorna (table_start, entry_count) para uma tabela de ponteiros 16-bit."""
    start, end = guess_pointer_table_bounds_16(rom, any_ptr_offset, little_endian=little_endian)
    return start, (end - start) // 2


def patch_pointer16(rom: bytearray, ptr_offset: int, value: int, little_endian: bool = True) -> None:
    """Escreve um ponteiro 16-bit no offset dado."""
    value &= 0xFFFF
    if little_endian:
        rom[ptr_offset:ptr_offset+2] = bytes([value & 0xFF, (value >> 8) & 0xFF])
    else:
        rom[ptr_offset:ptr_offset+2] = bytes([(value >> 8) & 0xFF, value & 0xFF])


def patch_bank_table_entry(rom: bytearray, bank_table_start: int, index: int, new_bank: int) -> None:
    """Atualiza 1 byte (bank) na bank table."""
    if bank_table_start is None or index is None:
        return
    if 0 <= bank_table_start + index < len(rom):
        rom[bank_table_start + index] = new_bank & 0xFF


def iter_pointer_refs16(
    rom: bytes,
    expected_value: int,
    little_endian: bool = True,
    mode: str = 'U16',
    valid_range: Tuple[int, int] = (0x0000, 0xFFFF),
) -> List[PointerRef]:
    """Encontra ocorrências de um ponteiro 16-bit com valor esperado e cria PointerRefs."""
    expected_value &= 0xFFFF
    b = (
        bytes([expected_value & 0xFF, (expected_value >> 8) & 0xFF])
        if little_endian
        else bytes([(expected_value >> 8) & 0xFF, expected_value & 0xFF])
    )
    offs = _find_all(rom, b)
    out: List[PointerRef] = []
    for off in offs:
        t0, t1 = guess_pointer_table_bounds_16(rom, off, little_endian=little_endian, valid_range=valid_range)
        idx = (off - t0) // 2
        out.append(PointerRef(ptr_offset=off, table_start=t0, index=idx, mode=mode))
    return out


def patch_banked_pointer3(
    rom: bytearray,
    ptr_offset: int,
    bank: int,
    addr16: int,
    mode: str = 'BANK_ADDR_LE',
) -> None:
    """Atualiza ponteiro 3 bytes (bank + addr16) ou (addr16 + bank)."""
    bank &= 0xFF
    addr16 &= 0xFFFF
    lo = addr16 & 0xFF
    hi = (addr16 >> 8) & 0xFF
    if mode == 'ADDR_LE_BANK':
        rom[ptr_offset:ptr_offset+3] = bytes([lo, hi, bank])
    else:
        rom[ptr_offset:ptr_offset+3] = bytes([bank, lo, hi])


def iter_banked_pointer3(
    rom: bytes,
    expected_bank: int,
    expected_addr16: int,
    mode: str = 'BANK_ADDR_LE',
) -> List[PointerRef]:
    """Encontra ocorrências de ponteiro 3 bytes (bank + addr16)."""
    expected_bank &= 0xFF
    expected_addr16 &= 0xFFFF
    lo = expected_addr16 & 0xFF
    hi = (expected_addr16 >> 8) & 0xFF
    needle = bytes([lo, hi, expected_bank]) if mode == 'ADDR_LE_BANK' else bytes([expected_bank, lo, hi])
    offs = _find_all(rom, needle)
    return [PointerRef(ptr_offset=o, table_start=None, index=None, mode=mode) for o in offs]
