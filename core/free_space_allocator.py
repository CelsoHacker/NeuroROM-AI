# -*- coding: utf-8 -*-
"""
================================================================================
FREE SPACE ALLOCATOR - Gerenciador de Alocacao Deterministico
================================================================================
Gerencia alocacao de espaco livre para realocacao de textos traduzidos.

Funcionalidades:
- Alocacao deterministica (user_regions -> default -> expansion)
- Suporte a regioes explicitas por console (config)
- Registro de todas as alocacoes para auditoria
- Expansao controlada de ROM quando suportado

NAO faz varredura cega da ROM - usa apenas regioes configuradas.
================================================================================
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .retro8_bank_tools import find_free_space_in_range, expand_rom_in_banks


@dataclass
class FreeRegion:
    """Uma regiao de espaco livre configurada."""
    start: int
    end: int
    source: str  # "user", "default", "expansion"
    comment: str = ""
    used_bytes: int = 0

    @property
    def available(self) -> int:
        return max(0, (self.end - self.start) - self.used_bytes)


@dataclass
class Allocation:
    """Registro de uma alocacao realizada."""
    offset: int
    size: int
    alignment: int
    item_uid: str
    region_source: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'offset': f"0x{self.offset:06X}",
            'size': self.size,
            'alignment': self.alignment,
            'item_uid': self.item_uid,
            'region_source': self.region_source,
            'timestamp': self.timestamp
        }


class FreeSpaceAllocator:
    """
    Gerenciador de alocacao de espaco livre para realocacao de textos.

    Estrategia:
    1. Tenta regioes do usuario (free_space_regions passadas explicitamente)
    2. Tenta regioes default do profile do console
    3. Se expansion_allowed, expande ROM e aloca no novo espaco

    Todas as alocacoes sao registradas para auditoria.
    """

    CONFIG_PATH = Path(__file__).parent.parent / "config" / "free_space_profiles.json"

    def __init__(
        self,
        rom_data: bytearray,
        console: str,
        user_regions: Optional[List[Dict]] = None,
        fill_byte: Optional[int] = None
    ):
        """
        Inicializa o alocador.

        Args:
            rom_data: Dados da ROM (bytearray para permitir modificacao)
            console: Tipo de console (SNES, NES, SMS, MD, GB, GBA)
            user_regions: Regioes livres definidas pelo usuario
                          [{"start": 0x1000, "end": 0x2000, "comment": "..."}, ...]
            fill_byte: Byte de preenchimento (override do profile)
        """
        self.rom_data = rom_data
        self.console = console.upper()
        self.original_size = len(rom_data)

        # Carrega profile do console
        self.profile = self._load_profile()

        # Override fill_byte se especificado
        if fill_byte is not None:
            self.profile['fill_byte'] = fill_byte

        # Inicializa regioes
        self.regions: List[FreeRegion] = []
        self._init_regions(user_regions)

        # Registro de alocacoes
        self.allocations: List[Allocation] = []

        # Estatisticas
        self.stats = {
            'total_allocated': 0,
            'user_region_allocations': 0,
            'default_region_allocations': 0,
            'expansion_allocations': 0,
            'expansion_bytes_added': 0,
            'failed_allocations': 0
        }

    def _load_profile(self) -> dict:
        """Carrega profile do console do arquivo de configuracao."""
        default_profile = {
            'bank_size': 16384,
            'default_regions': [],
            'expansion_allowed': False,
            'max_expansion_banks': 0,
            'fill_byte': 255,
            'alignment': 1,
            'addressing_modes': []
        }

        try:
            if self.CONFIG_PATH.exists():
                with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                    return profiles.get(self.console, default_profile)
        except Exception:
            pass

        return default_profile

    def _init_regions(self, user_regions: Optional[List[Dict]]):
        """Inicializa regioes livres."""
        # Adiciona regioes do usuario primeiro (maior prioridade)
        if user_regions:
            for region in user_regions:
                start = region.get('start', 0)
                end = region.get('end', 0)
                if isinstance(start, str):
                    start = int(start, 16)
                if isinstance(end, str):
                    end = int(end, 16)

                if end > start and end <= len(self.rom_data):
                    self.regions.append(FreeRegion(
                        start=start,
                        end=end,
                        source='user',
                        comment=region.get('comment', '')
                    ))

        # Adiciona regioes default do profile
        for region in self.profile.get('default_regions', []):
            start = region.get('start', 0)
            end = region.get('end', 0)
            if isinstance(start, str):
                start = int(start, 16)
            if isinstance(end, str):
                end = int(end, 16)

            if end > start and end <= len(self.rom_data):
                self.regions.append(FreeRegion(
                    start=start,
                    end=end,
                    source='default',
                    comment=region.get('comment', '')
                ))

    def allocate(
        self,
        size: int,
        alignment: Optional[int] = None,
        item_uid: str = ""
    ) -> Optional[int]:
        """
        Aloca espaco para um bloco de dados.

        Args:
            size: Tamanho necessario em bytes
            alignment: Alinhamento do offset (default: profile alignment)
            item_uid: Identificador do item (para auditoria)

        Returns:
            Offset alocado ou None se falhar
        """
        if size <= 0:
            return None

        if alignment is None:
            alignment = self.profile.get('alignment', 1)

        # Estrategia 1: Tentar regioes do usuario
        offset = self._try_allocate_from_regions(size, alignment, 'user')
        if offset is not None:
            self._register_allocation(offset, size, alignment, item_uid, 'user')
            self.stats['user_region_allocations'] += 1
            return offset

        # Estrategia 2: Tentar regioes default
        offset = self._try_allocate_from_regions(size, alignment, 'default')
        if offset is not None:
            self._register_allocation(offset, size, alignment, item_uid, 'default')
            self.stats['default_region_allocations'] += 1
            return offset

        # Estrategia 3: Tentar expansao
        if self.profile.get('expansion_allowed', False):
            offset = self._try_expand_and_allocate(size, alignment, item_uid)
            if offset is not None:
                self.stats['expansion_allocations'] += 1
                return offset

        # Falhou
        self.stats['failed_allocations'] += 1
        return None

    def _try_allocate_from_regions(
        self,
        size: int,
        alignment: int,
        source_filter: str
    ) -> Optional[int]:
        """Tenta alocar de regioes com source especifico."""
        fill_byte = self.profile.get('fill_byte', 0xFF)

        for region in self.regions:
            if region.source != source_filter:
                continue

            if region.available < size:
                continue

            # Calcula inicio disponivel (considerando bytes ja usados)
            search_start = region.start + region.used_bytes
            search_end = region.end

            # Procura espaco livre
            offset = find_free_space_in_range(
                self.rom_data,
                search_start,
                search_end,
                size,
                patterns=(fill_byte,),
                alignment=alignment,
                safety_slack=0
            )

            if offset is not None:
                region.used_bytes += size
                return offset

        return None

    def _try_expand_and_allocate(
        self,
        size: int,
        alignment: int,
        item_uid: str
    ) -> Optional[int]:
        """Expande ROM e aloca no novo espaco."""
        max_banks = self.profile.get('max_expansion_banks', 0)
        bank_size = self.profile.get('bank_size', 16384)
        fill_byte = self.profile.get('fill_byte', 0xFF)

        if max_banks <= 0:
            return None

        # Calcula quantos bancos ja foram adicionados
        expansion_so_far = len(self.rom_data) - self.original_size
        banks_added = expansion_so_far // bank_size if bank_size > 0 else 0

        if banks_added >= max_banks:
            return None

        # Expande ROM
        old_size, new_size = expand_rom_in_banks(
            self.rom_data,
            bank_size,
            size,
            fill=fill_byte
        )

        if new_size <= old_size:
            return None

        expansion_added = new_size - old_size
        self.stats['expansion_bytes_added'] += expansion_added

        # Aloca no inicio do novo espaco
        offset = old_size
        if alignment > 1:
            offset = (offset + alignment - 1) & ~(alignment - 1)

        # Cria regiao para o novo espaco
        self.regions.append(FreeRegion(
            start=old_size,
            end=new_size,
            source='expansion',
            comment=f"ROM expansion {banks_added + 1}",
            used_bytes=size
        ))

        self._register_allocation(offset, size, alignment, item_uid, 'expansion')
        return offset

    def _register_allocation(
        self,
        offset: int,
        size: int,
        alignment: int,
        item_uid: str,
        source: str
    ):
        """Registra uma alocacao."""
        allocation = Allocation(
            offset=offset,
            size=size,
            alignment=alignment,
            item_uid=item_uid,
            region_source=source
        )
        self.allocations.append(allocation)
        self.stats['total_allocated'] += size

    def register_in_place(self, offset: int, size: int, item_uid: str):
        """
        Registra uma escrita in-place (para auditoria).

        Usado quando o texto cabe no espaco original e nao precisa realocacao.
        """
        allocation = Allocation(
            offset=offset,
            size=size,
            alignment=1,
            item_uid=item_uid,
            region_source='in_place'
        )
        self.allocations.append(allocation)

    def get_allocation_map(self) -> List[dict]:
        """Retorna lista de alocacoes para incluir no mapping."""
        return [a.to_dict() for a in self.allocations]

    def get_stats(self) -> dict:
        """Retorna estatisticas de alocacao."""
        return {
            **self.stats,
            'original_rom_size': self.original_size,
            'current_rom_size': len(self.rom_data),
            'total_regions': len(self.regions),
            'total_allocations': len(self.allocations)
        }

    def check_overlap(self) -> List[Tuple[Allocation, Allocation]]:
        """
        Verifica se ha sobreposicao entre alocacoes.

        Returns:
            Lista de pares de alocacoes que se sobrepoem
        """
        overlaps = []
        sorted_allocs = sorted(self.allocations, key=lambda a: a.offset)

        for i in range(len(sorted_allocs) - 1):
            current = sorted_allocs[i]
            next_alloc = sorted_allocs[i + 1]

            current_end = current.offset + current.size
            if current_end > next_alloc.offset:
                overlaps.append((current, next_alloc))

        return overlaps

    def validate_allocations(self) -> Tuple[bool, List[str]]:
        """
        Valida todas as alocacoes.

        Returns:
            (valido, lista_de_erros)
        """
        errors = []

        # Verifica overlaps
        overlaps = self.check_overlap()
        for a1, a2 in overlaps:
            errors.append(
                f"OVERLAP: {a1.item_uid} (0x{a1.offset:06X}) e "
                f"{a2.item_uid} (0x{a2.offset:06X})"
            )

        # Verifica limites da ROM
        for alloc in self.allocations:
            if alloc.offset + alloc.size > len(self.rom_data):
                errors.append(
                    f"OUT_OF_BOUNDS: {alloc.item_uid} em 0x{alloc.offset:06X} "
                    f"excede tamanho da ROM"
                )

        return len(errors) == 0, errors


def create_allocator_for_console(
    rom_data: bytearray,
    console: str,
    user_regions: Optional[List[Dict]] = None
) -> FreeSpaceAllocator:
    """
    Factory function para criar alocador.

    Args:
        rom_data: Dados da ROM
        console: Tipo de console
        user_regions: Regioes livres opcionais

    Returns:
        FreeSpaceAllocator configurado
    """
    return FreeSpaceAllocator(rom_data, console, user_regions)
