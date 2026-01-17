# -*- coding: utf-8 -*-
"""
Memory Scanner - Leitura externa de memória de processos
Usa ReadProcessMemory (Windows API) para observação não-invasiva
"""

import ctypes
import struct
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

# Windows API definitions
kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


@dataclass
class MemoryRegion:
    """Região de memória detectada"""
    base_address: int
    size: int
    protection: int
    data: bytes


class MemoryScanner:
    """
    Scanner de memória para processos externos.

    Técnica: ReadProcessMemory (Windows API)
    Sem invasão, sem modificação, sem hooks.
    Apenas leitura externa para análise de QA/debug.
    """

    def __init__(self, process_name: Optional[str] = None, pid: Optional[int] = None):
        """
        Inicializa o scanner.

        Args:
            process_name: Nome do processo (ex: "snes9x.exe")
            pid: Process ID direto
        """
        self.process_name = process_name
        self.pid = pid
        self.handle = None
        self._last_scan_data = {}

    def attach(self) -> bool:
        """
        Anexa ao processo alvo.

        Returns:
            True se anexado com sucesso
        """
        try:
            if self.pid is None and self.process_name:
                self.pid = self._find_process_by_name(self.process_name)

            if self.pid is None:
                return False

            # Abrir processo com permissão de leitura
            self.handle = kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
                False,
                self.pid
            )

            return self.handle is not None

        except Exception:
            return False

    def detach(self):
        """Desanexa do processo"""
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """
        Lê região de memória do processo.

        Args:
            address: Endereço base
            size: Quantidade de bytes

        Returns:
            Bytes lidos ou None se falhar
        """
        if not self.handle:
            return None

        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()

        success = kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )

        if success and bytes_read.value == size:
            return buffer.raw
        return None

    def scan_range(self, start_address: int, end_address: int,
                   chunk_size: int = 4096) -> List[MemoryRegion]:
        """
        Escaneia range de memória em chunks.

        Args:
            start_address: Endereço inicial
            end_address: Endereço final
            chunk_size: Tamanho do chunk (padrão 4KB)

        Returns:
            Lista de regiões de memória lidas
        """
        regions = []
        current = start_address

        while current < end_address:
            size = min(chunk_size, end_address - current)
            data = self.read_memory(current, size)

            if data:
                regions.append(MemoryRegion(
                    base_address=current,
                    size=size,
                    protection=0,  # Placeholder
                    data=data
                ))

            current += size

        return regions

    def scan_changed_memory(self, start_address: int, end_address: int,
                           chunk_size: int = 4096) -> List[Tuple[int, bytes, bytes]]:
        """
        Detecta regiões que mudaram desde último scan.

        Returns:
            Lista de (address, old_data, new_data)
        """
        changes = []
        current = start_address

        while current < end_address:
            size = min(chunk_size, end_address - current)
            new_data = self.read_memory(current, size)

            if new_data:
                old_data = self._last_scan_data.get(current)

                if old_data and old_data != new_data:
                    changes.append((current, old_data, new_data))

                self._last_scan_data[current] = new_data

            current += size

        return changes

    def _find_process_by_name(self, name: str) -> Optional[int]:
        """
        Encontra PID por nome do processo.

        Args:
            name: Nome do executável

        Returns:
            PID ou None
        """
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == name.lower():
                    return proc.info['pid']
        except:
            pass
        return None

    def get_memory_info(self) -> Dict:
        """
        Retorna informações sobre o processo anexado.

        Returns:
            Dicionário com informações
        """
        if not self.handle:
            return {}

        return {
            'pid': self.pid,
            'process_name': self.process_name,
            'attached': True
        }

    def __enter__(self):
        """Context manager entry"""
        self.attach()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.detach()
