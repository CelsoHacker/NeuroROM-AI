# -*- coding: utf-8 -*-
"""
================================================================================
POINTER SCANNER - Detecção Automática de Tabelas de Ponteiros
================================================================================
Localiza e mapeia ponteiros que referenciam strings de texto através de:
- Detecção de padrões de endereçamento (16-bit, 24-bit, 32-bit)
- Análise de sequencialidade (ponteiros consecutivos)
- Validação de referências (ponteiro aponta para texto real)
- Reconstrução de tabelas de ponteiros

Essencial para reinserção segura de traduções
================================================================================
"""

import struct
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Pointer:
    """Representa um ponteiro encontrado na ROM."""
    offset: int           # Onde o ponteiro está na ROM
    value: int            # Valor do ponteiro
    size: int             # Tamanho em bytes (2, 3, ou 4)
    endianness: str       # 'little' ou 'big'
    target_offset: int    # Offset calculado para onde aponta
    points_to_text: bool  # Se aponta para região de texto conhecida
    confidence: float     # Score de confiança (0.0 - 1.0)

    def __repr__(self):
        return (f"<Pointer @0x{self.offset:06X} = 0x{self.value:06X} "
                f"→ 0x{self.target_offset:06X} ({self.size}B, {self.endianness}) "
                f"conf={self.confidence:.2f}>")


class PointerTable:
    """Representa uma tabela de ponteiros detectada."""

    def __init__(self, start_offset: int, pointer_size: int, endianness: str):
        self.start_offset = start_offset
        self.pointer_size = pointer_size
        self.endianness = endianness
        self.pointers: List[Pointer] = []
        self.confidence = 0.0

    def add_pointer(self, pointer: Pointer):
        """Adiciona ponteiro à tabela."""
        self.pointers.append(pointer)

    def calculate_confidence(self):
        """Calcula confiança da tabela baseado em métricas."""
        if not self.pointers:
            self.confidence = 0.0
            return

        # Fatores que aumentam confiança:
        # 1. Ponteiros consecutivos na memória
        # 2. Alto % de ponteiros apontando para texto
        # 3. Valores crescentes (textos sequenciais)

        # 1. Consecutividade
        if len(self.pointers) >= 2:
            gaps = [self.pointers[i+1].offset - self.pointers[i].offset
                   for i in range(len(self.pointers) - 1)]
            avg_gap = sum(gaps) / len(gaps)
            expected_gap = self.pointer_size
            gap_score = 1.0 if abs(avg_gap - expected_gap) < 1 else 0.5
        else:
            gap_score = 0.5

        # 2. Apontam para texto?
        text_pointing = sum(1 for p in self.pointers if p.points_to_text)
        text_ratio = text_pointing / len(self.pointers) if self.pointers else 0
        text_score = text_ratio

        # 3. Valores crescentes?
        if len(self.pointers) >= 3:
            values = [p.target_offset for p in self.pointers]
            ascending = sum(1 for i in range(len(values)-1) if values[i+1] > values[i])
            ascending_ratio = ascending / (len(values) - 1)
            order_score = ascending_ratio
        else:
            order_score = 0.5

        # Confiança final (média ponderada)
        self.confidence = (gap_score * 0.3 + text_score * 0.5 + order_score * 0.2)

    def __repr__(self):
        return (f"<PointerTable @0x{self.start_offset:06X} "
                f"count={len(self.pointers)} size={self.pointer_size}B "
                f"confidence={self.confidence:.2f}>")


class PointerScanner:
    """
    Scanner universal de ponteiros em ROMs.
    Detecta tabelas de ponteiros sem conhecimento prévio do jogo.
    """

    def __init__(self, rom_data: bytes, text_regions: Optional[List[Dict]] = None):
        """
        Args:
            rom_data: Dados brutos da ROM
            text_regions: Regiões conhecidas de texto (do TextScanner)
        """
        self.rom_data = rom_data
        self.text_regions = text_regions or []
        self.pointer_tables: List[PointerTable] = []
        self.all_pointers: List[Pointer] = []

        # Converte text_regions para set de ranges para busca rápida
        self.text_offsets = set()
        for region in self.text_regions:
            start = region.get('offset_dec', region.get('offset', 0))
            if isinstance(start, str):
                start = int(start, 16)
            length = region.get('length', 64)  # Assume comprimento padrão
            self.text_offsets.update(range(start, start + length))

    def scan(self, pointer_sizes: List[int] = [2, 3],
            endianness_modes: List[str] = ['little', 'big']) -> List[PointerTable]:
        """
        Executa varredura completa buscando ponteiros.

        Args:
            pointer_sizes: Tamanhos de ponteiros para testar (2, 3, 4 bytes)
            endianness_modes: Modos de byte order para testar

        Returns:
            Lista de tabelas de ponteiros ordenadas por confiança
        """
        print(f"\n🔗 POINTER SCANNER - Automatic Pointer Table Detection")
        print(f"{'='*70}")

        # Testa todas as combinações de tamanho e endianness
        for size in pointer_sizes:
            for endian in endianness_modes:
                print(f"Scanning for {size}-byte {endian}-endian pointers...")
                self._scan_pointers(size, endian)

        # Agrupa ponteiros em tabelas
        print(f"\nGrouping pointers into tables...")
        self._identify_tables()

        # Calcula confiança de cada tabela
        for table in self.pointer_tables:
            table.calculate_confidence()

        # Ordena por confiança
        self.pointer_tables.sort(key=lambda t: t.confidence, reverse=True)

        print(f"\n✅ Found {len(self.all_pointers)} total pointers")
        print(f"✅ Identified {len(self.pointer_tables)} pointer tables")
        print(f"{'='*70}\n")

        return self.pointer_tables

    def _scan_pointers(self, size: int, endianness: str):
        """Varre ROM buscando ponteiros de tamanho e endianness específicos."""
        rom_size = len(self.rom_data)

        # Varre ROM byte a byte
        for offset in range(0, rom_size - size):
            # Lê bytes
            data = self.rom_data[offset:offset + size]

            # Interpreta como ponteiro
            if endianness == 'little':
                if size == 2:
                    ptr_value = struct.unpack('<H', data)[0]
                elif size == 3:
                    ptr_value = struct.unpack('<I', data + b'\x00')[0]  # Pad to 4 bytes
                elif size == 4:
                    ptr_value = struct.unpack('<I', data)[0]
            else:  # big endian
                if size == 2:
                    ptr_value = struct.unpack('>H', data)[0]
                elif size == 3:
                    ptr_value = struct.unpack('>I', b'\x00' + data)[0]
                elif size == 4:
                    ptr_value = struct.unpack('>I', data)[0]

            # Calcula offset alvo (heurísticas para diferentes mapeamentos)
            target_candidates = self._calculate_target_offsets(ptr_value, offset, size)

            # Para cada candidato, verifica se é válido
            for target_offset in target_candidates:
                if 0 <= target_offset < rom_size:
                    # Verifica se aponta para região de texto conhecida
                    points_to_text = target_offset in self.text_offsets

                    # Calcula confiança deste ponteiro
                    confidence = self._calculate_pointer_confidence(
                        ptr_value, target_offset, points_to_text
                    )

                    # Só aceita ponteiros com confiança mínima
                    if confidence >= 0.3:  # Threshold ajustável
                        pointer = Pointer(
                            offset=offset,
                            value=ptr_value,
                            size=size,
                            endianness=endianness,
                            target_offset=target_offset,
                            points_to_text=points_to_text,
                            confidence=confidence
                        )
                        self.all_pointers.append(pointer)

    def _calculate_target_offsets(self, ptr_value: int, ptr_offset: int,
                                  size: int) -> List[int]:
        """
        Calcula possíveis offsets alvo baseado em heurísticas de mapeamento.

        SNES LoROM: pointer & 0x7FFF + (bank << 15)
        SNES HiROM: pointer & 0xFFFF + (bank << 16)
        Absoluto: pointer diretamente
        Relativo: ptr_offset + pointer
        """
        candidates = []

        # 1. Absoluto (valor direto)
        candidates.append(ptr_value)

        # 2. LoROM SNES (banco $00-$7F, ROM em $8000-$FFFF)
        if size >= 2:
            # Assume bank $00 (mais comum para ponteiros de texto)
            lorom_offset = (ptr_value & 0x7FFF)
            candidates.append(lorom_offset)

            # Tenta outros bancos comuns
            for bank in [0x01, 0x02, 0x03, 0x0E, 0x0F]:
                lorom_offset = (ptr_value & 0x7FFF) + (bank << 15)
                candidates.append(lorom_offset)

        # 3. HiROM SNES
        if size >= 3:
            # Extrai banco e offset
            bank = (ptr_value >> 16) & 0xFF
            offset_in_bank = ptr_value & 0xFFFF

            # HiROM: bancos $C0+ mapeiam diretamente
            if bank >= 0xC0:
                hirom_offset = ((bank - 0xC0) << 16) + offset_in_bank
                candidates.append(hirom_offset)

        # 4. Relativo ao ponteiro (menos comum)
        if size == 2 and ptr_value < 0x8000:  # Deslocamentos pequenos
            relative_offset = ptr_offset + ptr_value
            candidates.append(relative_offset)

        return candidates

    def _calculate_pointer_confidence(self, ptr_value: int, target_offset: int,
                                     points_to_text: bool) -> float:
        """
        Calcula score de confiança de que isso é um ponteiro real.

        Fatores:
        - Aponta para texto conhecido (+0.5)
        - Valor está em range plausível (+0.2)
        - Alvo não está em região de padding (+0.3)
        """
        confidence = 0.0

        # 1. Aponta para texto?
        if points_to_text:
            confidence += 0.5

        # 2. Valor plausível? (não muito pequeno, não muito grande)
        if 0x100 <= ptr_value <= 0xFFFFFF:
            confidence += 0.2

        # 3. Alvo não é região de padding (0x00 ou 0xFF repetidos)
        if target_offset < len(self.rom_data) - 16:
            target_data = self.rom_data[target_offset:target_offset + 16]
            padding_count = target_data.count(0x00) + target_data.count(0xFF)
            if padding_count < 14:  # Menos de 14/16 bytes de padding
                confidence += 0.3

        return min(confidence, 1.0)

    def _identify_tables(self):
        """
        Agrupa ponteiros individuais em tabelas baseado em proximidade.

        Ponteiros consecutivos com mesmo tamanho/endianness provavelmente
        fazem parte da mesma tabela.
        """
        if not self.all_pointers:
            return

        # Ordena ponteiros por offset
        sorted_ptrs = sorted(self.all_pointers, key=lambda p: p.offset)

        # Agrupa ponteiros próximos
        current_table = None

        for pointer in sorted_ptrs:
            # Se não há tabela atual ou ponteiro está muito longe
            if current_table is None:
                current_table = PointerTable(
                    pointer.offset, pointer.size, pointer.endianness
                )
                current_table.add_pointer(pointer)
            else:
                # Verifica se pertence à tabela atual
                last_ptr = current_table.pointers[-1]
                expected_next = last_ptr.offset + current_table.pointer_size

                # Se está na posição esperada e tem mesmos atributos
                if (pointer.offset == expected_next and
                    pointer.size == current_table.pointer_size and
                    pointer.endianness == current_table.endianness):
                    current_table.add_pointer(pointer)
                else:
                    # Finaliza tabela anterior
                    if len(current_table.pointers) >= 3:  # Mínimo 3 ponteiros
                        self.pointer_tables.append(current_table)

                    # Inicia nova tabela
                    current_table = PointerTable(
                        pointer.offset, pointer.size, pointer.endianness
                    )
                    current_table.add_pointer(pointer)

        # Adiciona última tabela
        if current_table and len(current_table.pointers) >= 3:
            self.pointer_tables.append(current_table)

    def export_tables(self, output_path: str):
        """Exporta tabelas de ponteiros para JSON."""
        import json
        from datetime import datetime

        export_data = {
            'scan_timestamp': datetime.now().isoformat(),
            'total_pointers': len(self.all_pointers),
            'total_tables': len(self.pointer_tables),
            'pointer_tables': []
        }

        for i, table in enumerate(self.pointer_tables, 1):
            table_data = {
                'table_id': i,
                'start_offset': hex(table.start_offset),
                'pointer_count': len(table.pointers),
                'pointer_size': table.pointer_size,
                'endianness': table.endianness,
                'confidence': round(table.confidence, 3),
                'pointers': [
                    {
                        'offset': hex(p.offset),
                        'value': hex(p.value),
                        'target': hex(p.target_offset),
                        'points_to_text': p.points_to_text,
                        'confidence': round(p.confidence, 3)
                    }
                    for p in table.pointers[:50]  # Limita para não ficar gigante
                ]
            }
            export_data['pointer_tables'].append(table_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        print(f"✅ Exported pointer tables to: {output_path}")

    def print_summary(self, n: int = 5):
        """Exibe resumo das N melhores tabelas."""
        print(f"\n📍 TOP {n} POINTER TABLES")
        print(f"{'='*70}")

        for i, table in enumerate(self.pointer_tables[:n], 1):
            print(f"\n{i}. Table at 0x{table.start_offset:06X}")
            print(f"   Pointers:    {len(table.pointers)}")
            print(f"   Size:        {table.pointer_size} bytes")
            print(f"   Endianness:  {table.endianness}")
            print(f"   Confidence:  {table.confidence:.3f}")
            print(f"   Points to text: {sum(1 for p in table.pointers if p.points_to_text)}/{len(table.pointers)}")

            # Mostra primeiros 3 ponteiros
            print(f"   Sample pointers:")
            for ptr in table.pointers[:3]:
                print(f"      {ptr}")

        print(f"\n{'='*70}\n")


def scan_pointers_in_rom(rom_path: str, text_regions: Optional[List[Dict]] = None) -> PointerScanner:
    """
    Função de conveniência para scan direto.

    Args:
        rom_path: Caminho da ROM
        text_regions: Regiões de texto do TextScanner (opcional)

    Returns:
        PointerScanner com tabelas detectadas
    """
    with open(rom_path, 'rb') as f:
        data = f.read()
        # Remove SMC header se presente
        if len(data) % 1024 == 512:
            data = data[512:]

    scanner = PointerScanner(data, text_regions)
    scanner.scan(pointer_sizes=[2, 3], endianness_modes=['little'])  # SNES usa little-endian
    scanner.print_summary(5)

    # Exporta
    import os
    output_path = os.path.splitext(rom_path)[0] + '_pointer_tables.json'
    scanner.export_tables(output_path)

    return scanner


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pointer_scanner.py <rom_file>")
        sys.exit(1)

    rom_file = sys.argv[1]
    scan_pointers_in_rom(rom_file)
