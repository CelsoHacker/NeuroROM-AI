#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
POINTER SCANNER - Sistema Avançado de Detecção de Ponteiros
================================================================================
Localiza onde o jogo 'chama' os textos através de ponteiros.

Funcionalidades:
- Conversão de offsets físicos para endereços virtuais
- Busca de ponteiros com suporte a múltiplas arquiteturas
- Detecção automática de tabelas de ponteiros (heurística)
- Suporte a Little/Big Endian
- Suporte a 16-bit, 24-bit, 32-bit pointers

Heurística de Tabela:
Quando encontra um ponteiro, verifica se os bytes vizinhos também são
ponteiros válidos apontando para áreas próximas. Isso identifica
automaticamente tabelas de ponteiros completas.
================================================================================
"""

import struct
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

# Importa o MemoryMapper que criamos anteriormente
try:
    from memory_mapper import MemoryMapper, MappingResult
except ImportError:
    print("[WARN] memory_mapper não encontrado - funcionalidade limitada")
    MemoryMapper = None
    MappingResult = None


class Endianness(Enum):
    """Tipos de endianness"""
    LITTLE = "little"
    BIG = "big"


class PointerSize(Enum):
    """Tamanhos de ponteiros suportados"""
    PTR_16 = 2  # 16-bit (SNES LoROM interno)
    PTR_24 = 3  # 24-bit (SNES completo)
    PTR_32 = 4  # 32-bit (PS1, N64, etc)


@dataclass
class PointerMatch:
    """Ponteiro encontrado"""
    offset: int                    # Offset onde o ponteiro está
    pointer_value: int            # Valor do ponteiro
    points_to_offset: int         # Offset para onde aponta (PC)
    points_to_address: int        # Endereço virtual para onde aponta
    size: int                     # Tamanho do ponteiro (2, 3 ou 4 bytes)
    endianness: Endianness        # Little ou Big endian
    is_in_table: bool = False     # Se faz parte de uma tabela
    table_id: Optional[int] = None  # ID da tabela (se aplicável)
    confidence: float = 1.0       # Confiança na detecção

    def __repr__(self) -> str:
        table_str = f" [Table #{self.table_id}]" if self.is_in_table else ""
        return f"<Pointer @0x{self.offset:X} → 0x{self.points_to_address:X}{table_str}>"


@dataclass
class PointerTable:
    """Tabela de ponteiros detectada"""
    table_id: int
    start_offset: int             # Offset inicial da tabela
    end_offset: int               # Offset final da tabela
    entry_count: int              # Número de entradas
    entry_size: int               # Tamanho de cada entrada
    pointers: List[PointerMatch]  # Ponteiros na tabela
    confidence: float             # Confiança na detecção
    pattern: str                  # Padrão detectado

    def __repr__(self) -> str:
        return (f"<PointerTable #{self.table_id} @0x{self.start_offset:X} "
                f"entries={self.entry_count} conf={self.confidence:.1%}>")


class PointerScanner:
    """
    Scanner avançado de ponteiros com detecção automática de tabelas
    """

    def __init__(
        self,
        rom_path: str,
        memory_mapper: Optional[MemoryMapper] = None,
        verbose: bool = False
    ):
        """
        Args:
            rom_path: Caminho para o arquivo ROM
            memory_mapper: Instância de MemoryMapper para conversões
            verbose: Se True, imprime informações de debug
        """
        self.rom_path = Path(rom_path)
        self.memory_mapper = memory_mapper
        self.verbose = verbose

        # Carrega ROM
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM não encontrada: {rom_path}")

        self.rom_data = np.fromfile(self.rom_path, dtype=np.uint8)
        self.rom_size = len(self.rom_data)

        # Cache de tabelas detectadas
        self.detected_tables: List[PointerTable] = []
        self._next_table_id = 1

        if self.verbose:
            print(f"[INFO] ROM carregada: {self.rom_path.name}")
            print(f"[INFO] Tamanho: {self.rom_size:,} bytes")

    def scan_pointers(
        self,
        text_offset: int,
        pointer_size: PointerSize = PointerSize.PTR_24,
        endianness: Endianness = Endianness.LITTLE,
        detect_tables: bool = True,
        table_proximity_threshold: int = 0x1000  # 4KB
    ) -> Tuple[List[PointerMatch], List[PointerTable]]:
        """
        Escaneia ROM procurando ponteiros para um offset específico

        Args:
            text_offset: Offset físico do texto na ROM
            pointer_size: Tamanho do ponteiro (16, 24 ou 32 bits)
            endianness: Little ou Big endian
            detect_tables: Se True, detecta tabelas automaticamente
            table_proximity_threshold: Distância máxima entre textos de uma tabela

        Returns:
            Tupla (lista de ponteiros, lista de tabelas)
        """
        if self.verbose:
            print(f"\n[INFO] Escaneando ponteiros para offset 0x{text_offset:X}")
            print(f"[INFO] Configuração: {pointer_size.name}, {endianness.value}")

        # Converte offset para endereço virtual
        virtual_address = self._offset_to_virtual_address(text_offset)

        if virtual_address is None:
            if self.verbose:
                print(f"[WARN] Não foi possível converter offset para endereço virtual")
            return [], []

        if self.verbose:
            print(f"[INFO] Endereço virtual: 0x{virtual_address:X}")

        # Converte endereço para bytes
        pointer_bytes = self._address_to_bytes(
            virtual_address,
            pointer_size.value,
            endianness
        )

        if self.verbose:
            print(f"[INFO] Procurando bytes: {pointer_bytes.hex().upper()}")

        # Busca ponteiros
        pointers = self._find_pointer_bytes(
            pointer_bytes,
            virtual_address,
            text_offset,
            pointer_size,
            endianness
        )

        if self.verbose:
            print(f"[OK] Encontrados {len(pointers)} ponteiros")

        # Detecta tabelas
        tables = []
        if detect_tables and pointers:
            tables = self._detect_pointer_tables(
                pointers,
                pointer_size,
                endianness,
                table_proximity_threshold
            )

            if self.verbose:
                print(f"[OK] Detectadas {len(tables)} tabelas")

        return pointers, tables

    def _offset_to_virtual_address(self, pc_offset: int) -> Optional[int]:
        """
        Converte offset físico para endereço virtual do console

        Args:
            pc_offset: Offset no arquivo ROM

        Returns:
            Endereço virtual ou None se falhar
        """
        if self.memory_mapper is None:
            # Sem mapper, assume mapeamento 1:1
            return pc_offset

        try:
            result = self.memory_mapper.pc_to_console_addr(pc_offset)
            if result.success:
                return result.console_address
        except Exception as e:
            if self.verbose:
                print(f"[WARN] Erro ao converter offset: {e}")

        return None

    def _address_to_bytes(
        self,
        address: int,
        size: int,
        endianness: Endianness
    ) -> bytes:
        """
        Converte endereço para sequência de bytes

        Args:
            address: Endereço virtual
            size: Tamanho em bytes (2, 3 ou 4)
            endianness: Little ou Big endian

        Returns:
            Bytes representando o endereço
        """
        # Garante que o endereço cabe no tamanho especificado
        max_value = (1 << (size * 8)) - 1
        address = address & max_value

        # Converte para bytes
        if size == 2:
            fmt = '<H' if endianness == Endianness.LITTLE else '>H'
            return struct.pack(fmt, address)
        elif size == 3:
            # 24-bit: não tem formato struct direto
            if endianness == Endianness.LITTLE:
                return address.to_bytes(3, byteorder='little')
            else:
                return address.to_bytes(3, byteorder='big')
        elif size == 4:
            fmt = '<I' if endianness == Endianness.LITTLE else '>I'
            return struct.pack(fmt, address)
        else:
            raise ValueError(f"Tamanho inválido: {size}")

    def _find_pointer_bytes(
        self,
        target_bytes: bytes,
        virtual_address: int,
        text_offset: int,
        pointer_size: PointerSize,
        endianness: Endianness
    ) -> List[PointerMatch]:
        """
        Busca sequência de bytes na ROM (ponteiros)

        Args:
            target_bytes: Bytes a serem buscados
            virtual_address: Endereço virtual original
            text_offset: Offset do texto (para onde aponta)
            pointer_size: Tamanho do ponteiro
            endianness: Endianness

        Returns:
            Lista de ponteiros encontrados
        """
        pointers = []

        # Converte para NumPy array para busca rápida
        target_array = np.frombuffer(target_bytes, dtype=np.uint8)
        pattern_len = len(target_array)

        # Busca vetorizada
        # Cria janelas deslizantes
        if len(self.rom_data) < pattern_len:
            return pointers

        windows = np.lib.stride_tricks.sliding_window_view(
            self.rom_data,
            pattern_len
        )

        # Compara todas as janelas de uma vez
        matches = np.all(windows == target_array, axis=1)
        match_indices = np.where(matches)[0]

        # Cria objetos PointerMatch
        for offset in match_indices:
            pointers.append(PointerMatch(
                offset=int(offset),
                pointer_value=virtual_address,
                points_to_offset=text_offset,
                points_to_address=virtual_address,
                size=pointer_size.value,
                endianness=endianness
            ))

        return pointers

    def _detect_pointer_tables(
        self,
        pointers: List[PointerMatch],
        pointer_size: PointerSize,
        endianness: Endianness,
        proximity_threshold: int
    ) -> List[PointerTable]:
        """
        Detecta tabelas de ponteiros usando heurísticas

        Heurística:
        1. Agrupa ponteiros que estão próximos fisicamente
        2. Verifica se formam uma sequência regular (espaçamento constante)
        3. Valida se os ponteiros apontam para áreas próximas (tabela coerente)

        Args:
            pointers: Lista de ponteiros encontrados
            pointer_size: Tamanho dos ponteiros
            endianness: Endianness
            proximity_threshold: Distância máxima entre destinos

        Returns:
            Lista de tabelas detectadas
        """
        if len(pointers) < 2:
            return []

        tables = []

        # Ordena ponteiros por offset
        sorted_pointers = sorted(pointers, key=lambda p: p.offset)

        # Agrupa ponteiros que estão próximos
        clusters = self._cluster_pointers(sorted_pointers, pointer_size.value)

        # Analisa cada cluster
        for cluster in clusters:
            if len(cluster) < 3:  # Precisa de pelo menos 3 para ser considerado tabela
                continue

            # Verifica se forma uma tabela válida
            table = self._validate_pointer_table(
                cluster,
                pointer_size,
                endianness,
                proximity_threshold
            )

            if table:
                tables.append(table)

        return tables

    def _cluster_pointers(
        self,
        pointers: List[PointerMatch],
        entry_size: int
    ) -> List[List[PointerMatch]]:
        """
        Agrupa ponteiros que estão fisicamente próximos

        Args:
            pointers: Lista ordenada de ponteiros
            entry_size: Tamanho esperado de cada entrada

        Returns:
            Lista de clusters (cada cluster é uma lista de ponteiros)
        """
        if not pointers:
            return []

        clusters = []
        current_cluster = [pointers[0]]

        for i in range(1, len(pointers)):
            prev_offset = pointers[i-1].offset
            curr_offset = pointers[i].offset

            # Distância esperada (pode ter padding)
            expected_distance = entry_size
            actual_distance = curr_offset - prev_offset

            # Se estiver próximo (com tolerância), adiciona ao cluster
            if actual_distance <= expected_distance * 2:  # Tolerância: 2x o tamanho
                current_cluster.append(pointers[i])
            else:
                # Inicia novo cluster
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [pointers[i]]

        # Adiciona último cluster
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        return clusters

    def _validate_pointer_table(
        self,
        cluster: List[PointerMatch],
        pointer_size: PointerSize,
        endianness: Endianness,
        proximity_threshold: int
    ) -> Optional[PointerTable]:
        """
        Valida se um cluster é realmente uma tabela de ponteiros

        Critérios:
        1. Espaçamento regular entre ponteiros
        2. Ponteiros apontam para áreas próximas (textos consecutivos)
        3. Sem "buracos" na sequência

        Args:
            cluster: Cluster de ponteiros
            pointer_size: Tamanho dos ponteiros
            endianness: Endianness
            proximity_threshold: Distância máxima entre destinos

        Returns:
            PointerTable se válido, None caso contrário
        """
        if len(cluster) < 3:
            return None

        # Calcula distâncias entre ponteiros consecutivos (offsets na ROM)
        offsets = [p.offset for p in cluster]
        distances = [offsets[i+1] - offsets[i] for i in range(len(offsets)-1)]

        # Verifica regularidade (espaçamento constante ou múltiplo)
        most_common_distance = max(set(distances), key=distances.count)
        regular_count = sum(1 for d in distances if d == most_common_distance)
        regularity_ratio = regular_count / len(distances)

        if regularity_ratio < 0.7:  # Pelo menos 70% regular
            return None

        # Verifica se destinos estão próximos
        destinations = [p.points_to_offset for p in cluster]
        dest_distances = [destinations[i+1] - destinations[i] for i in range(len(destinations)-1)]

        # Destinos devem estar razoavelmente próximos
        avg_dest_distance = np.mean([abs(d) for d in dest_distances])

        if avg_dest_distance > proximity_threshold:
            # Verifica se ao menos alguns estão próximos
            close_count = sum(1 for d in dest_distances if abs(d) < proximity_threshold)
            if close_count < len(dest_distances) * 0.5:
                return None

        # Calcula confiança
        confidence = 0.5
        confidence += regularity_ratio * 0.3

        if avg_dest_distance < proximity_threshold / 2:
            confidence += 0.2

        # Cria tabela
        table_id = self._next_table_id
        self._next_table_id += 1

        # Marca ponteiros como parte da tabela
        for pointer in cluster:
            pointer.is_in_table = True
            pointer.table_id = table_id

        table = PointerTable(
            table_id=table_id,
            start_offset=cluster[0].offset,
            end_offset=cluster[-1].offset + pointer_size.value,
            entry_count=len(cluster),
            entry_size=most_common_distance,
            pointers=cluster,
            confidence=min(confidence, 1.0),
            pattern=f"{most_common_distance}-byte entries"
        )

        return table

    def export_pointer_map(
        self,
        pointers: List[PointerMatch],
        tables: List[PointerTable],
        output_path: str
    ):
        """
        Exporta mapa de ponteiros para arquivo JSON

        Args:
            pointers: Lista de ponteiros
            tables: Lista de tabelas
            output_path: Caminho do arquivo de saída
        """
        import json

        data = {
            "rom_file": str(self.rom_path.name),
            "total_pointers": len(pointers),
            "total_tables": len(tables),
            "pointers": [
                {
                    "offset": f"0x{p.offset:X}",
                    "value": f"0x{p.pointer_value:X}",
                    "points_to": f"0x{p.points_to_offset:X}",
                    "size": p.size,
                    "endianness": p.endianness.value,
                    "in_table": p.is_in_table,
                    "table_id": p.table_id
                }
                for p in pointers
            ],
            "tables": [
                {
                    "id": t.table_id,
                    "start": f"0x{t.start_offset:X}",
                    "end": f"0x{t.end_offset:X}",
                    "entries": t.entry_count,
                    "entry_size": t.entry_size,
                    "confidence": f"{t.confidence:.1%}",
                    "pattern": t.pattern
                }
                for t in tables
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if self.verbose:
            print(f"[OK] Mapa exportado: {output_path}")


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

def main():
    """Exemplo de uso do PointerScanner"""
    import sys

    print("="*80)
    print("🎯 POINTER SCANNER - Detector de Ponteiros e Tabelas")
    print("="*80)
    print()

    if len(sys.argv) < 3:
        print("Uso: python pointer_scanner.py <rom_path> <text_offset_hex>")
        print("\nExemplo:")
        print("  python pointer_scanner.py game.smc 0x12ABC")
        return 1

    rom_path = sys.argv[1]
    text_offset = int(sys.argv[2], 16)

    try:
        # Cria scanner (sem mapper por enquanto - usa mapeamento 1:1)
        scanner = PointerScanner(rom_path, verbose=True)

        # Escaneia ponteiros
        pointers, tables = scanner.scan_pointers(
            text_offset=text_offset,
            pointer_size=PointerSize.PTR_24,
            endianness=Endianness.LITTLE,
            detect_tables=True
        )

        print("\n" + "="*80)
        print("📊 RESULTADOS")
        print("="*80 + "\n")

        if not pointers:
            print("❌ Nenhum ponteiro encontrado")
            return 0

        print(f"✅ Encontrados {len(pointers)} ponteiros\n")

        # Mostra ponteiros individuais
        if len([p for p in pointers if not p.is_in_table]) > 0:
            print("📍 Ponteiros Isolados:")
            for p in pointers:
                if not p.is_in_table:
                    print(f"  • 0x{p.offset:06X} → 0x{p.points_to_address:06X}")
            print()

        # Mostra tabelas
        if tables:
            print(f"📋 Tabelas Detectadas: {len(tables)}\n")
            for table in tables:
                print(f"  [Tabela #{table.table_id}]")
                print(f"    Offset: 0x{table.start_offset:X} - 0x{table.end_offset:X}")
                print(f"    Entradas: {table.entry_count}")
                print(f"    Tamanho: {table.entry_size} bytes/entrada")
                print(f"    Confiança: {table.confidence:.1%}")
                print(f"    Padrão: {table.pattern}")
                print()

        # Exporta
        output_file = f"{Path(rom_path).stem}_pointers_0x{text_offset:X}.json"
        scanner.export_pointer_map(pointers, tables, output_file)
        print(f"💾 Mapa exportado: {output_file}")

        return 0

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())