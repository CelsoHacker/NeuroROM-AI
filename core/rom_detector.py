#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Detector - Sistema Profissional de Detecção de ROMs
========================================================

Detecta tipo de console/sistema a partir de arquivos de ROM.
Resolve conflitos de extensão através de análise de conteúdo.

Autor: ROM Translation Framework
Versão: 1.0.0
"""

import os
from typing import Tuple, List, Optional
from pathlib import Path


class ROMDetector:
    """Detector profissional de tipos de ROM."""

    def __init__(self):
        """Inicializa o detector com mapeamentos de extensões."""

        # Mapeamento de extensões para possíveis tipos (com prioridades)
        self.extension_priority_map = {
            # ========== CONSOLES ESPECÍFICOS (SEM AMBIGUIDADE) ==========
            # SNES
            '.smc': ['SNES'],
            '.sfc': ['SNES'],

            # Game Boy
            '.gba': ['GBA'],
            '.gb': ['GB'],
            '.gbc': ['GBC'],

            # NES
            '.nes': ['NES'],
            '.fds': ['NES'],

            # Sega Genesis/Mega Drive
            '.gen': ['GENESIS'],
            '.md': ['GENESIS'],
            '.smd': ['GENESIS'],

            # Sega Master System
            '.sms': ['MASTER_SYSTEM'],

            # Sega 32X
            '.32x': ['GENESIS_32X'],

            # Sega Saturn
            '.scd': ['SEGA_CD'],

            # Nintendo 64
            '.n64': ['N64'],
            '.z64': ['N64'],
            '.v64': ['N64'],

            # Nintendo DS
            '.nds': ['NDS'],
            '.dsi': ['NDS'],

            # Nintendo 3DS
            '.3ds': ['3DS'],
            '.cia': ['3DS'],
            '.cxi': ['3DS'],

            # Nintendo Switch
            '.nsp': ['SWITCH'],
            '.xci': ['SWITCH'],

            # Nintendo GameCube
            '.gcm': ['GAMECUBE'],

            # Wii
            '.wbfs': ['WII'],
            '.ciso': ['WII'],

            # Wii U
            '.wud': ['WIIU'],
            '.wux': ['WIIU'],
            '.rpx': ['WIIU'],

            # Xbox
            '.xbe': ['XBOX'],

            # Xbox 360
            '.xex': ['XBOX360'],

            # Neo Geo
            '.neo': ['NEO_GEO'],
            '.ng': ['NEO_GEO'],

            # Atari
            '.a26': ['ATARI_2600'],
            '.a52': ['ATARI_5200'],
            '.a78': ['ATARI_7800'],

            # ========== EXTENSÕES AMBÍGUAS (PRECISAM ANÁLISE) ==========
            # ISO - Pode ser vários consoles
            '.iso': ['PS1', 'PS2', 'GAMECUBE', 'WII', 'DREAMCAST', 'PSP', 'UNKNOWN_ISO'],

            # BIN - Pode ser PS1, Sega CD, Saturn, ou genérico
            '.bin': ['PS1', 'SEGA_CD', 'SATURN', 'UNKNOWN_ROM'],

            # EXE - Pode ser Windows ou MS-DOS
            '.exe': ['WINDOWS', 'MSDOS'],

            # PKG - Pode ser PS3, PS4, ou PS Vita
            '.pkg': ['PS4', 'PS3', 'PSVITA'],

            # SS - Pode ser Saturn ROM ou Save State
            '.ss': ['SATURN', 'SAVE_STATE'],

            # ========== ARQUIVOS AUXILIARES ==========
            # CUE (sempre acompanha BIN)
            '.cue': ['CUE_SHEET'],

            # Imagens genéricas
            '.img': ['UNKNOWN_ROM'],
            '.rom': ['UNKNOWN_ROM'],

            # Arquivos compactados
            '.zip': ['ARCHIVE'],
            '.rar': ['ARCHIVE'],
            '.7z': ['ARCHIVE'],
            '.gz': ['ARCHIVE'],

            # Documentos
            '.txt': ['DOCUMENT'],
            '.pdf': ['DOCUMENT'],
            '.nfo': ['DOCUMENT'],

            # Imagens
            '.jpg': ['IMAGE'],
            '.jpeg': ['IMAGE'],
            '.png': ['IMAGE'],
            '.gif': ['IMAGE'],

            # Saves
            '.sav': ['SAVE_FILE'],
            '.srm': ['SAVE_FILE'],
            '.state': ['SAVE_STATE'],
        }

        # Tamanhos típicos de cada tipo de mídia (em bytes)
        self.typical_sizes = {
            'PS1': (650_000_000, 750_000_000),      # 650-750 MB
            'PS2': (4_000_000_000, 5_000_000_000),  # 4-5 GB (DVD)
            'GAMECUBE': (1_300_000_000, 1_500_000_000),  # 1.4 GB
            'WII': (4_000_000_000, 9_000_000_000),  # 4.7 GB ou 8.5 GB
            'DREAMCAST': (1_000_000_000, 1_200_000_000),  # ~1 GB
            'PSP': (500_000_000, 2_000_000_000),    # 500 MB - 1.8 GB
        }

    def detect(self, filepath: str) -> Tuple[str, float]:
        """
        Detecta o tipo de arquivo ROM.

        Args:
            filepath: Caminho para o arquivo

        Returns:
            Tupla (tipo_detectado, confiança)
            confiança: 0.0 (baixa) a 1.0 (alta)
        """
        if not os.path.exists(filepath):
            return 'FILE_NOT_FOUND', 0.0

        ext = Path(filepath).suffix.lower()

        # Verifica se a extensão está no mapa
        if ext not in self.extension_priority_map:
            return 'TOTAL_UNKNOWN', 0.0

        possible_types = self.extension_priority_map[ext]

        # Se só há uma possibilidade, retorna com alta confiança
        if len(possible_types) == 1:
            return possible_types[0], 1.0

        # Se há múltiplas possibilidades, analisa conteúdo
        return self._analyze_content(filepath, ext, possible_types)

    def _analyze_content(self, filepath: str, ext: str,
                        possible_types: List[str]) -> Tuple[str, float]:
        """
        Analisa conteúdo do arquivo para desambiguar tipo.

        Args:
            filepath: Caminho do arquivo
            ext: Extensão do arquivo
            possible_types: Lista de tipos possíveis

        Returns:
            Tupla (tipo_detectado, confiança)
        """
        # Análise específica por extensão
        if ext == '.iso':
            return self._analyze_iso(filepath, possible_types)
        elif ext == '.bin':
            return self._analyze_bin(filepath, possible_types)
        elif ext == '.exe':
            return self._analyze_exe(filepath, possible_types)
        elif ext == '.pkg':
            return self._analyze_pkg(filepath, possible_types)
        elif ext == '.ss':
            return self._analyze_ss(filepath, possible_types)

        # Se não há análise específica, retorna o primeiro com baixa confiança
        return possible_types[0], 0.5

    def _analyze_iso(self, filepath: str, possible_types: List[str]) -> Tuple[str, float]:
        """
        Analisa arquivo ISO para determinar console.

        Estratégia:
        1. Verifica tamanho do arquivo
        2. Lê header para identificar assinatura
        """
        try:
            size = os.path.getsize(filepath)

            # Análise por tamanho
            for console, (min_size, max_size) in self.typical_sizes.items():
                if console in possible_types and min_size <= size <= max_size:
                    # Verifica header para confirmar
                    with open(filepath, 'rb') as f:
                        header = f.read(2048)

                        # PS1: verifica assinatura
                        if console == 'PS1':
                            if b'PlayStation' in header or b'PLAYSTATION' in header:
                                return 'PS1', 0.95

                        # PS2: verifica estrutura de DVD
                        elif console == 'PS2':
                            if b'DVD' in header or size > 3_500_000_000:
                                return 'PS2', 0.9

                        # GameCube: verifica magic bytes
                        elif console == 'GAMECUBE':
                            # GameCube ISO começa com 0xC2339F3D
                            if header[:4] == b'\xC2\x33\x9F\x3D':
                                return 'GAMECUBE', 0.98

                        # Wii: similar ao GameCube mas maior
                        elif console == 'WII':
                            if header[:4] == b'\x5D\x1C\x9E\xA3':  # Magic Wii
                                return 'WII', 0.98

                        # Dreamcast: verifica header
                        elif console == 'DREAMCAST':
                            if b'SEGA' in header[:16]:
                                return 'DREAMCAST', 0.95

            # Se não identificou por tamanho/header, retorna primeiro
            return possible_types[0], 0.3

        except Exception as e:
            print(f"Erro ao analisar ISO: {e}")
            return 'UNKNOWN_ISO', 0.1

    def _analyze_bin(self, filepath: str, possible_types: List[str]) -> Tuple[str, float]:
        """Analisa arquivo BIN."""
        try:
            size = os.path.getsize(filepath)

            # PS1: geralmente 650-750 MB
            if 600_000_000 <= size <= 800_000_000:
                # Verifica se há arquivo .cue correspondente
                cue_file = filepath.replace('.bin', '.cue')
                if os.path.exists(cue_file):
                    return 'PS1', 0.9

            # Sega CD: similar ao PS1 mas menor
            if 300_000_000 <= size <= 700_000_000:
                with open(filepath, 'rb') as f:
                    header = f.read(256)
                    if b'SEGADISCSYSTEM' in header or b'SEGA' in header[:16]:
                        return 'SEGA_CD', 0.95

            # Saturn: maior que Sega CD
            if 400_000_000 <= size <= 800_000_000:
                with open(filepath, 'rb') as f:
                    header = f.read(256)
                    if b'SEGA SATURN' in header:
                        return 'SATURN', 0.95

            return 'UNKNOWN_ROM', 0.3

        except Exception as e:
            print(f"Erro ao analisar BIN: {e}")
            return 'UNKNOWN_ROM', 0.1

    def _analyze_exe(self, filepath: str, possible_types: List[str]) -> Tuple[str, float]:
        """Analisa arquivo EXE (Windows vs MS-DOS)."""
        try:
            with open(filepath, 'rb') as f:
                header = f.read(64)

                # PE header = Windows
                if b'PE\x00\x00' in header:
                    return 'WINDOWS', 0.95

                # MZ header sem PE = MS-DOS
                if header[:2] == b'MZ':
                    # Verifica se é MS-DOS puro
                    if b'This program cannot be run in DOS mode' not in header:
                        return 'MSDOS', 0.8
                    else:
                        return 'WINDOWS', 0.9

            return 'WINDOWS', 0.5  # Default para Windows

        except Exception as e:
            print(f"Erro ao analisar EXE: {e}")
            return 'WINDOWS', 0.3

    def _analyze_pkg(self, filepath: str, possible_types: List[str]) -> Tuple[str, float]:
        """Analisa arquivo PKG (PS3 vs PS4 vs PS Vita)."""
        try:
            size = os.path.getsize(filepath)

            # PS4: geralmente maior (jogos modernos)
            if size > 10_000_000_000:  # > 10 GB
                return 'PS4', 0.8

            # PS3: tamanho médio
            if 1_000_000_000 <= size <= 10_000_000_000:
                return 'PS3', 0.7

            # PS Vita: menor
            if size < 1_000_000_000:
                return 'PSVITA', 0.7

            # Default: PS4 (mais recente)
            return 'PS4', 0.5

        except Exception as e:
            print(f"Erro ao analisar PKG: {e}")
            return 'PS4', 0.3

    def _analyze_ss(self, filepath: str, possible_types: List[str]) -> Tuple[str, float]:
        """Analisa arquivo .ss (Saturn ROM vs Save State)."""
        try:
            size = os.path.getsize(filepath)

            # Save states são geralmente pequenos (< 10 MB)
            if size < 10_000_000:
                return 'SAVE_STATE', 0.9

            # Saturn ROMs são grandes (> 100 MB)
            if size > 100_000_000:
                with open(filepath, 'rb') as f:
                    header = f.read(256)
                    if b'SEGA SATURN' in header:
                        return 'SATURN', 0.95
                return 'SATURN', 0.7

            return 'SAVE_STATE', 0.5

        except Exception as e:
            print(f"Erro ao analisar .ss: {e}")
            return 'SAVE_STATE', 0.3

    def get_category(self, file_type: str) -> str:
        """
        Retorna a categoria do tipo de arquivo.

        Args:
            file_type: Tipo detectado

        Returns:
            Categoria (ROM, ARCHIVE, DOCUMENT, etc.)
        """
        rom_types = {
            'SNES', 'GBA', 'GB', 'GBC', 'NES', 'GENESIS', 'MASTER_SYSTEM',
            'GENESIS_32X', 'SEGA_CD', 'SATURN', 'DREAMCAST', 'N64', 'NDS',
            '3DS', 'PS1', 'PS2', 'PS3', 'PS4', 'PSVITA', 'PSP', 'SWITCH',
            'GAMECUBE', 'WII', 'WIIU', 'XBOX', 'XBOX360', 'NEO_GEO',
            'ATARI_2600', 'ATARI_5200', 'ATARI_7800', 'MSDOS', 'WINDOWS'
        }

        if file_type in rom_types:
            return 'ROM'
        elif file_type in ['ARCHIVE', 'CUE_SHEET']:
            return 'AUXILIARY'
        elif file_type in ['DOCUMENT', 'IMAGE']:
            return 'EXTRA'
        elif file_type in ['SAVE_FILE', 'SAVE_STATE']:
            return 'SAVE'
        elif file_type in ['UNKNOWN_ROM', 'UNKNOWN_ISO']:
            return 'UNKNOWN_ROM'
        else:
            return 'UNKNOWN'


def test_detector():
    """Função de teste básica."""
    detector = ROMDetector()

    # Testes com arquivos fictícios
    test_files = [
        ('test.smc', 'SNES'),
        ('test.iso', 'UNKNOWN_ISO'),  # Precisa análise
        ('test.exe', 'WINDOWS'),
        ('test.pkg', 'PS4'),
        ('test.ss', 'SAVE_STATE'),  # Precisa análise
    ]

    print("🧪 Testes Básicos:")
    print("=" * 60)

    for filename, expected in test_files:
        ext = Path(filename).suffix.lower()
        possible = detector.extension_priority_map.get(ext, ['UNKNOWN'])
        print(f"{filename:20s} → Possíveis: {possible}")

    print("\n✅ Testes completados!")


if __name__ == '__main__':
    test_detector()
