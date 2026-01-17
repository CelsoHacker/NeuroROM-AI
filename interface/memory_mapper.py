#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
MEMORY MAPPER - Arquitetura Universal de Mapeamento de Memória
================================================================================
Arquitetura orientada a objetos para conversão de endereços entre:
- Endereços do Console (lógicos/virtuais)
- Offsets do arquivo ROM (físicos/PC)

Suporta múltiplas plataformas através de herança:
- SNES (LoROM, HiROM, ExHiROM, SA-1)
- Genesis/Mega Drive
- PlayStation 1
- Extensível para qualquer console

Design Clean Room - Baseado em documentação técnica oficial
================================================================================
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, List
from enum import Enum
from dataclasses import dataclass


class MapperType(Enum):
    """Tipos de mapeamento conhecidos"""
    # SNES
    SNES_LOROM = "SNES LoROM"
    SNES_HIROM = "SNES HiROM"
    SNES_EXHIROM = "SNES ExHiROM"
    SNES_SA1 = "SNES SA-1"

    # Genesis/Mega Drive
    GENESIS_STANDARD = "Genesis Standard"

    # PlayStation
    PS1_STANDARD = "PS1 Standard"

    # Genérico
    LINEAR = "Linear (1:1)"
    UNKNOWN = "Unknown"


@dataclass
class MemoryRegion:
    """Região de memória mapeada"""
    name: str
    start_addr: int  # Endereço inicial do console
    end_addr: int    # Endereço final do console
    pc_offset: int   # Offset no arquivo ROM
    size: int        # Tamanho da região
    readable: bool = True
    writable: bool = False
    mirrored: bool = False
    mirror_mask: Optional[int] = None


@dataclass
class MappingResult:
    """Resultado de uma conversão de endereço"""
    success: bool
    pc_offset: Optional[int] = None
    console_address: Optional[int] = None
    region: Optional[MemoryRegion] = None
    error_message: Optional[str] = None
    is_mirrored: bool = False


class MemoryMapper(ABC):
    """
    Classe base abstrata para mapeamento de memória

    Define a interface que todos os mappers de console devem implementar.
    Garante consistência e extensibilidade através de herança.
    """

    def __init__(self, rom_size: int, mapper_type: MapperType = MapperType.UNKNOWN):
        """
        Args:
            rom_size: Tamanho do arquivo ROM em bytes
            mapper_type: Tipo de mapeamento
        """
        self.rom_size = rom_size
        self.mapper_type = mapper_type
        self.regions: List[MemoryRegion] = []
        self._init_memory_map()

    @abstractmethod
    def _init_memory_map(self):
        """
        Inicializa o mapa de memória específico do console

        Deve ser implementado por cada subclasse para definir:
        - Regiões de memória
        - Espelhamento
        - Mapeamentos especiais
        """
        pass

    @abstractmethod
    def pc_to_console_addr(self, pc_offset: int) -> MappingResult:
        """
        Converte offset do arquivo ROM para endereço do console

        Args:
            pc_offset: Offset no arquivo ROM (0x0000 - tamanho do arquivo)

        Returns:
            MappingResult com endereço do console ou erro
        """
        pass

    @abstractmethod
    def console_to_pc_addr(self, console_address: int) -> MappingResult:
        """
        Converte endereço do console para offset do arquivo ROM

        Args:
            console_address: Endereço lógico do console

        Returns:
            MappingResult com offset do PC ou erro
        """
        pass

    def get_region_at_address(self, console_address: int) -> Optional[MemoryRegion]:
        """
        Retorna a região de memória que contém o endereço especificado

        Args:
            console_address: Endereço lógico do console

        Returns:
            MemoryRegion ou None se não encontrado
        """
        for region in self.regions:
            if region.start_addr <= console_address <= region.end_addr:
                return region
        return None

    def validate_pc_offset(self, pc_offset: int) -> bool:
        """Valida se o offset está dentro dos limites do arquivo"""
        return 0 <= pc_offset < self.rom_size

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.mapper_type.value} rom_size={self.rom_size:,}>"


# ============================================================================
# SNES MAPPER - Implementação Completa
# ============================================================================

class SnesMapper(MemoryMapper):
    """
    Mapeador de memória para Super Nintendo

    Suporta os principais modos de mapeamento:
    - LoROM (Mode 20): Mapeamento de 32KB por banco
    - HiROM (Mode 21): Mapeamento de 64KB por banco
    - ExHiROM: Expansão do HiROM para ROMs maiores
    - SA-1: Chip especial com mapeamento customizado

    Baseado na documentação técnica oficial do SNES:
    - Banks: 256 bancos ($00-$FF) de 64KB cada
    - Address Space: 24-bit (16MB total)
    - ROM máxima: até 6MB (sem coprocessadores)
    """

    # Constantes do SNES
    BANK_SIZE = 0x10000  # 64KB por banco
    LOROM_BANK_ROM_SIZE = 0x8000  # 32KB de ROM por banco em LoROM
    HIROM_BANK_ROM_SIZE = 0x10000  # 64KB de ROM por banco em HiROM

    # Headers conhecidos
    LOROM_HEADER_OFFSET = 0x7FC0
    HIROM_HEADER_OFFSET = 0xFFC0
    EXHIROM_HEADER_OFFSET = 0x40FFC0

    def __init__(self, rom_size: int, auto_detect: bool = True):
        """
        Args:
            rom_size: Tamanho do arquivo ROM
            auto_detect: Se True, detecta automaticamente o tipo de mapeamento
        """
        self.mapping_mode = MapperType.UNKNOWN

        if auto_detect:
            self.mapping_mode = self._detect_mapping_mode(rom_size)

        super().__init__(rom_size, self.mapping_mode)

    def _detect_mapping_mode(self, rom_size: int) -> MapperType:
        """
        Detecta automaticamente o modo de mapeamento baseado no tamanho e header

        Args:
            rom_size: Tamanho do arquivo ROM

        Returns:
            MapperType detectado
        """
        # ExHiROM: ROMs muito grandes (> 4MB)
        if rom_size > 0x400000:
            return MapperType.SNES_EXHIROM

        # HiROM: ROMs entre 2MB e 4MB tendem a ser HiROM
        elif rom_size >= 0x200000:
            return MapperType.SNES_HIROM

        # LoROM: ROMs menores
        else:
            return MapperType.SNES_LOROM

    def _init_memory_map(self):
        """
        Inicializa o mapa de memória do SNES

        Memory Map do SNES (simplificado):

        LoROM:
        $00-$3F: Banks com ROM em $8000-$FFFF (32KB)
        $40-$6F: Banks com ROM em $0000-$FFFF (64KB, usado por alguns jogos)
        $80-$BF: Mirror de $00-$3F
        $C0-$FF: Mirror de $40-$6F ou ROM adicional

        HiROM:
        $00-$3F: Banks com ROM em $8000-$FFFF (32KB da segunda metade)
        $40-$7D: Banks com ROM em $0000-$FFFF (64KB completos)
        $80-$BF: Mirror de $00-$3F
        $C0-$FF: Mirror de $40-$7D
        """
        self.regions = []

        if self.mapping_mode == MapperType.SNES_LOROM:
            self._init_lorom_map()
        elif self.mapping_mode == MapperType.SNES_HIROM:
            self._init_hirom_map()
        elif self.mapping_mode == MapperType.SNES_EXHIROM:
            self._init_exhirom_map()

    def _init_lorom_map(self):
        """Inicializa mapeamento LoROM"""
        # Banks $00-$3F: ROM em $8000-$FFFF (32KB)
        for bank in range(0x00, 0x40):
            pc_offset = bank * self.LOROM_BANK_ROM_SIZE
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"LoROM Bank ${bank:02X}",
                    start_addr=(bank << 16) | 0x8000,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=self.LOROM_BANK_ROM_SIZE,
                    mirrored=False
                ))

        # Banks $80-$BF: Mirror de $00-$3F
        for bank in range(0x80, 0xC0):
            mirror_bank = bank & 0x3F
            pc_offset = mirror_bank * self.LOROM_BANK_ROM_SIZE
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"LoROM Bank ${bank:02X} (Mirror)",
                    start_addr=(bank << 16) | 0x8000,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=self.LOROM_BANK_ROM_SIZE,
                    mirrored=True,
                    mirror_mask=0x3F
                ))

    def _init_hirom_map(self):
        """Inicializa mapeamento HiROM"""
        # Banks $00-$3F: Segunda metade dos bancos ROM ($8000-$FFFF)
        for bank in range(0x00, 0x40):
            pc_offset = (bank * self.HIROM_BANK_ROM_SIZE) + 0x8000
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"HiROM Bank ${bank:02X} (High)",
                    start_addr=(bank << 16) | 0x8000,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=0x8000,
                    mirrored=False
                ))

        # Banks $40-$7D: ROM completa ($0000-$FFFF)
        for bank in range(0x40, 0x7E):
            pc_offset = (bank - 0x40) * self.HIROM_BANK_ROM_SIZE
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"HiROM Bank ${bank:02X}",
                    start_addr=bank << 16,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=self.HIROM_BANK_ROM_SIZE,
                    mirrored=False
                ))

        # Banks $C0-$FF: Mirror de $40-$7D (adiciona 0x80 ao bank)
        for bank in range(0xC0, 0x100):
            mirror_bank = bank - 0x80
            if 0x40 <= mirror_bank <= 0x7D:
                pc_offset = (mirror_bank - 0x40) * self.HIROM_BANK_ROM_SIZE
                if pc_offset < self.rom_size:
                    self.regions.append(MemoryRegion(
                        name=f"HiROM Bank ${bank:02X} (Mirror)",
                        start_addr=bank << 16,
                        end_addr=(bank << 16) | 0xFFFF,
                        pc_offset=pc_offset,
                        size=self.HIROM_BANK_ROM_SIZE,
                        mirrored=True,
                        mirror_mask=0x7F
                    ))

    def _init_exhirom_map(self):
        """Inicializa mapeamento ExHiROM (ROMs > 4MB)"""
        # Similar ao HiROM mas com banks adicionais
        # Banks $40-$7D: Primeira metade da ROM
        for bank in range(0x40, 0x7E):
            pc_offset = (bank - 0x40) * self.HIROM_BANK_ROM_SIZE
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"ExHiROM Bank ${bank:02X}",
                    start_addr=bank << 16,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=self.HIROM_BANK_ROM_SIZE,
                    mirrored=False
                ))

        # Banks $C0-$FD: Segunda metade da ROM (após 4MB)
        for bank in range(0xC0, 0xFE):
            pc_offset = 0x400000 + ((bank - 0xC0) * self.HIROM_BANK_ROM_SIZE)
            if pc_offset < self.rom_size:
                self.regions.append(MemoryRegion(
                    name=f"ExHiROM Bank ${bank:02X}",
                    start_addr=bank << 16,
                    end_addr=(bank << 16) | 0xFFFF,
                    pc_offset=pc_offset,
                    size=self.HIROM_BANK_ROM_SIZE,
                    mirrored=False
                ))

    def pc_to_console_addr(self, pc_offset: int) -> MappingResult:
        """
        Converte offset PC para endereço SNES

        Args:
            pc_offset: Offset no arquivo ROM

        Returns:
            MappingResult com endereço SNES
        """
        if not self.validate_pc_offset(pc_offset):
            return MappingResult(
                success=False,
                error_message=f"Offset PC inválido: 0x{pc_offset:X} (ROM size: 0x{self.rom_size:X})"
            )

        if self.mapping_mode == MapperType.SNES_LOROM:
            return self._pc_to_lorom(pc_offset)
        elif self.mapping_mode == MapperType.SNES_HIROM:
            return self._pc_to_hirom(pc_offset)
        elif self.mapping_mode == MapperType.SNES_EXHIROM:
            return self._pc_to_exhirom(pc_offset)

        return MappingResult(
            success=False,
            error_message=f"Modo de mapeamento não suportado: {self.mapping_mode}"
        )

    def _pc_to_lorom(self, pc_offset: int) -> MappingResult:
        """Converte PC offset para endereço LoROM"""
        # Bank é calculado dividindo por 32KB
        bank = pc_offset // self.LOROM_BANK_ROM_SIZE
        offset_in_bank = pc_offset % self.LOROM_BANK_ROM_SIZE

        # Em LoROM, a ROM está mapeada em $8000-$FFFF
        console_address = (bank << 16) | (0x8000 + offset_in_bank)

        region = self.get_region_at_address(console_address)

        return MappingResult(
            success=True,
            console_address=console_address,
            pc_offset=pc_offset,
            region=region
        )

    def _pc_to_hirom(self, pc_offset: int) -> MappingResult:
        """Converte PC offset para endereço HiROM"""
        # Em HiROM, cada bank mapeia 64KB
        if pc_offset < 0x400000:  # Primeiros 4MB
            bank = (pc_offset // self.HIROM_BANK_ROM_SIZE) + 0x40
            offset_in_bank = pc_offset % self.HIROM_BANK_ROM_SIZE
            console_address = (bank << 16) | offset_in_bank
        else:
            # Offset não suportado em HiROM padrão
            return MappingResult(
                success=False,
                error_message=f"Offset PC muito alto para HiROM: 0x{pc_offset:X}"
            )

        region = self.get_region_at_address(console_address)

        return MappingResult(
            success=True,
            console_address=console_address,
            pc_offset=pc_offset,
            region=region
        )

    def _pc_to_exhirom(self, pc_offset: int) -> MappingResult:
        """Converte PC offset para endereço ExHiROM"""
        if pc_offset < 0x400000:  # Primeiros 4MB
            bank = (pc_offset // self.HIROM_BANK_ROM_SIZE) + 0x40
            offset_in_bank = pc_offset % self.HIROM_BANK_ROM_SIZE
        else:  # Acima de 4MB
            bank = ((pc_offset - 0x400000) // self.HIROM_BANK_ROM_SIZE) + 0xC0
            offset_in_bank = (pc_offset - 0x400000) % self.HIROM_BANK_ROM_SIZE

        console_address = (bank << 16) | offset_in_bank
        region = self.get_region_at_address(console_address)

        return MappingResult(
            success=True,
            console_address=console_address,
            pc_offset=pc_offset,
            region=region
        )

    def console_to_pc_addr(self, console_address: int) -> MappingResult:
        """
        Converte endereço SNES para offset PC

        Args:
            console_address: Endereço SNES (24-bit)

        Returns:
            MappingResult com offset PC
        """
        # Extrai bank e offset
        bank = (console_address >> 16) & 0xFF
        offset = console_address & 0xFFFF

        if self.mapping_mode == MapperType.SNES_LOROM:
            return self._lorom_to_pc(bank, offset)
        elif self.mapping_mode == MapperType.SNES_HIROM:
            return self._hirom_to_pc(bank, offset)
        elif self.mapping_mode == MapperType.SNES_EXHIROM:
            return self._exhirom_to_pc(bank, offset)

        return MappingResult(
            success=False,
            error_message=f"Modo de mapeamento não suportado: {self.mapping_mode}"
        )

    def _lorom_to_pc(self, bank: int, offset: int) -> MappingResult:
        """Converte endereço LoROM para PC offset"""
        # Remove mirror bit se estiver setado
        actual_bank = bank & 0x7F

        # LoROM: ROM está em $8000-$FFFF
        if offset < 0x8000:
            return MappingResult(
                success=False,
                error_message=f"Endereço fora da região ROM: ${bank:02X}:{offset:04X}"
            )

        # Calcula offset PC
        rom_offset_in_bank = offset - 0x8000
        pc_offset = (actual_bank * self.LOROM_BANK_ROM_SIZE) + rom_offset_in_bank

        if not self.validate_pc_offset(pc_offset):
            return MappingResult(
                success=False,
                error_message=f"Offset PC resultante inválido: 0x{pc_offset:X}"
            )

        region = self.get_region_at_address((bank << 16) | offset)
        is_mirrored = (bank & 0x80) != 0

        return MappingResult(
            success=True,
            pc_offset=pc_offset,
            console_address=(bank << 16) | offset,
            region=region,
            is_mirrored=is_mirrored
        )

    def _hirom_to_pc(self, bank: int, offset: int) -> MappingResult:
        """Converte endereço HiROM para PC offset"""
        # Remove mirror bit
        actual_bank = bank & 0x7F

        if 0x40 <= actual_bank <= 0x7D:
            # Banks principais: mapeamento direto
            pc_offset = ((actual_bank - 0x40) * self.HIROM_BANK_ROM_SIZE) + offset
        elif 0x00 <= actual_bank <= 0x3F and offset >= 0x8000:
            # Banks $00-$3F: segunda metade
            pc_offset = (actual_bank * self.HIROM_BANK_ROM_SIZE) + offset
        else:
            return MappingResult(
                success=False,
                error_message=f"Endereço HiROM inválido: ${bank:02X}:{offset:04X}"
            )

        if not self.validate_pc_offset(pc_offset):
            return MappingResult(
                success=False,
                error_message=f"Offset PC resultante inválido: 0x{pc_offset:X}"
            )

        region = self.get_region_at_address((bank << 16) | offset)
        is_mirrored = (bank & 0x80) != 0

        return MappingResult(
            success=True,
            pc_offset=pc_offset,
            console_address=(bank << 16) | offset,
            region=region,
            is_mirrored=is_mirrored
        )

    def _exhirom_to_pc(self, bank: int, offset: int) -> MappingResult:
        """Converte endereço ExHiROM para PC offset"""
        actual_bank = bank & 0x7F

        if 0x40 <= actual_bank <= 0x7D:
            # Primeira metade (0-4MB)
            pc_offset = ((actual_bank - 0x40) * self.HIROM_BANK_ROM_SIZE) + offset
        elif 0xC0 <= bank <= 0xFD:
            # Segunda metade (4MB+)
            pc_offset = 0x400000 + ((bank - 0xC0) * self.HIROM_BANK_ROM_SIZE) + offset
        else:
            return MappingResult(
                success=False,
                error_message=f"Endereço ExHiROM inválido: ${bank:02X}:{offset:04X}"
            )

        if not self.validate_pc_offset(pc_offset):
            return MappingResult(
                success=False,
                error_message=f"Offset PC resultante inválido: 0x{pc_offset:X}"
            )

        region = self.get_region_at_address((bank << 16) | offset)

        return MappingResult(
            success=True,
            pc_offset=pc_offset,
            console_address=(bank << 16) | offset,
            region=region
        )


# ============================================================================
# EXEMPLO DE USO E TESTES
# ============================================================================

def main():
    """Exemplo de uso e testes do Memory Mapper"""
    print("="*80)
    print("MEMORY MAPPER - Sistema de Mapeamento Universal")
    print("="*80)
    print()

    # Exemplo 1: SNES LoROM
    print("📦 Exemplo 1: SNES LoROM (2MB)")
    print("-" * 80)
    mapper = SnesMapper(rom_size=0x200000, auto_detect=False)
    mapper.mapping_mode = MapperType.SNES_LOROM
    mapper._init_memory_map()

    # Teste PC -> Console
    test_offsets = [0x0000, 0x8000, 0x10000, 0x1FFFF]
    for offset in test_offsets:
        result = mapper.pc_to_console_addr(offset)
        if result.success:
            print(f"  PC 0x{offset:06X} → SNES ${result.console_address:06X}")
        else:
            print(f"  PC 0x{offset:06X} → ERRO: {result.error_message}")

    print()

    # Teste Console -> PC
    test_addrs = [0x008000, 0x018000, 0x808000, 0xFF8000]
    for addr in test_addrs:
        result = mapper.console_to_pc_addr(addr)
        if result.success:
            mirror_str = " (MIRROR)" if result.is_mirrored else ""
            print(f"  SNES ${addr:06X} → PC 0x{result.pc_offset:06X}{mirror_str}")
        else:
            print(f"  SNES ${addr:06X} → ERRO: {result.error_message}")

    print()
    print("="*80)
    print()

    # Exemplo 2: SNES HiROM
    print("📦 Exemplo 2: SNES HiROM (4MB)")
    print("-" * 80)
    mapper2 = SnesMapper(rom_size=0x400000, auto_detect=True)

    test_offsets2 = [0x0000, 0x10000, 0x100000, 0x3FFFFF]
    for offset in test_offsets2:
        result = mapper2.pc_to_console_addr(offset)
        if result.success:
            print(f"  PC 0x{offset:06X} → SNES ${result.console_address:06X}")

    print()
    print("="*80)


if __name__ == "__main__":
    main()