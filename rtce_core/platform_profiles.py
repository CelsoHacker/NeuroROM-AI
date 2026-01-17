# -*- coding: utf-8 -*-
"""
Platform Profiles - Perfis configuráveis para diferentes consoles/sistemas
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PlatformProfile:
    """Perfil de plataforma para RTCE"""
    name: str
    ram_size: int
    ram_start: int
    encodings: List[str]
    entropy_min: float
    entropy_max: float
    tile_table: Optional[str] = None
    notes: str = ""


class PlatformProfiles:
    """
    Gerenciador de perfis de plataforma.

    Perfis são configurações específicas para cada console/sistema,
    definindo onde e como procurar texto na memória.
    """

    # ====================================================================
    # PERFIS DE PLATAFORMA (CONFIGURÁVEIS)
    # ====================================================================

    PROFILES: Dict[str, PlatformProfile] = {
        # ==================== NINTENDO ====================
        'SNES': PlatformProfile(
            name='Super Nintendo (SNES)',
            ram_size=131072,  # 128KB
            ram_start=0x7E0000,  # WRAM no endereço padrão
            encodings=['ascii', 'shift_jis'],
            entropy_min=3.5,
            entropy_max=6.5,
            tile_table='snes_default.tbl',
            notes='LoROM/HiROM - WRAM 128KB'
        ),

        'NES': PlatformProfile(
            name='Nintendo Entertainment System (NES)',
            ram_size=2048,  # 2KB
            ram_start=0x0000,
            encodings=['ascii'],
            entropy_min=3.0,
            entropy_max=6.0,
            tile_table='nes_default.tbl',
            notes='RAM interna 2KB + possível expansion'
        ),

        'N64': PlatformProfile(
            name='Nintendo 64',
            ram_size=4194304,  # 4MB (padrão) ou 8MB
            ram_start=0x80000000,
            encodings=['ascii', 'shift_jis'],
            entropy_min=3.5,
            entropy_max=7.0,
            notes='RDRAM 4-8MB - Big Endian'
        ),

        'GBA': PlatformProfile(
            name='Game Boy Advance',
            ram_size=262144,  # 256KB
            ram_start=0x02000000,  # EWRAM
            encodings=['ascii'],
            entropy_min=3.0,
            entropy_max=6.5,
            tile_table='gba_default.tbl',
            notes='EWRAM 256KB + IWRAM 32KB'
        ),

        'NDS': PlatformProfile(
            name='Nintendo DS',
            ram_size=4194304,  # 4MB
            ram_start=0x02000000,
            encodings=['ascii', 'utf-16le'],
            entropy_min=3.5,
            entropy_max=7.0,
            notes='Main RAM 4MB'
        ),

        # ==================== SEGA ====================
        'GENESIS': PlatformProfile(
            name='Sega Genesis / Mega Drive',
            ram_size=65536,  # 64KB
            ram_start=0xFF0000,
            encodings=['ascii'],
            entropy_min=3.0,
            entropy_max=6.5,
            tile_table='genesis_default.tbl',
            notes='RAM 64KB - Big Endian'
        ),

        'MASTER_SYSTEM': PlatformProfile(
            name='Sega Master System',
            ram_size=8192,  # 8KB
            ram_start=0xC000,
            encodings=['ascii'],
            entropy_min=3.0,
            entropy_max=6.0,
            notes='RAM 8KB'
        ),

        'SATURN': PlatformProfile(
            name='Sega Saturn',
            ram_size=2097152,  # 2MB
            ram_start=0x00200000,
            encodings=['ascii', 'shift_jis'],
            entropy_min=3.5,
            entropy_max=7.0,
            notes='WRAM 2MB'
        ),

        'DREAMCAST': PlatformProfile(
            name='Sega Dreamcast',
            ram_size=16777216,  # 16MB
            ram_start=0x8C000000,
            encodings=['ascii', 'shift_jis', 'utf-16le'],
            entropy_min=4.0,
            entropy_max=7.5,
            notes='Main RAM 16MB'
        ),

        # ==================== SONY ====================
        'PS1': PlatformProfile(
            name='PlayStation 1',
            ram_size=2097152,  # 2MB
            ram_start=0x80000000,
            encodings=['ascii', 'shift_jis'],
            entropy_min=3.5,
            entropy_max=7.0,
            notes='Main RAM 2MB - Little Endian'
        ),

        'PS2': PlatformProfile(
            name='PlayStation 2',
            ram_size=33554432,  # 32MB
            ram_start=0x00100000,
            encodings=['ascii', 'shift_jis', 'utf-16le'],
            entropy_min=4.0,
            entropy_max=7.5,
            notes='Main RAM 32MB'
        ),

        # ==================== PC ====================
        'PC_WINDOWS': PlatformProfile(
            name='PC Game (Windows)',
            ram_size=0,  # Dinâmico
            ram_start=0,  # Dinâmico
            encodings=['ascii', 'utf-8', 'utf-16le', 'latin-1'],
            entropy_min=3.5,
            entropy_max=7.5,
            notes='Memória dinâmica - requer heap scanning'
        ),
    }

    @classmethod
    def get_profile(cls, platform_name: str) -> Optional[PlatformProfile]:
        """
        Obtém perfil de plataforma.

        Args:
            platform_name: Nome da plataforma (ex: 'SNES', 'NES')

        Returns:
            PlatformProfile ou None se não encontrado
        """
        return cls.PROFILES.get(platform_name.upper())

    @classmethod
    def list_platforms(cls) -> List[str]:
        """
        Lista todas as plataformas suportadas.

        Returns:
            Lista de nomes de plataformas
        """
        return list(cls.PROFILES.keys())

    @classmethod
    def add_custom_profile(cls, key: str, profile: PlatformProfile):
        """
        Adiciona perfil customizado.

        Args:
            key: Identificador único
            profile: Perfil configurado
        """
        cls.PROFILES[key.upper()] = profile

    @classmethod
    def load_from_json(cls, json_path: str):
        """
        Carrega perfis de arquivo JSON.

        Args:
            json_path: Caminho do JSON
        """
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)

        for key, profile_data in data.items():
            profile = PlatformProfile(**profile_data)
            cls.add_custom_profile(key, profile)

    @classmethod
    def save_to_json(cls, json_path: str):
        """
        Salva perfis em JSON.

        Args:
            json_path: Caminho de saída
        """
        import json
        data = {}

        for key, profile in cls.PROFILES.items():
            data[key] = {
                'name': profile.name,
                'ram_size': profile.ram_size,
                'ram_start': profile.ram_start,
                'encodings': profile.encodings,
                'entropy_min': profile.entropy_min,
                'entropy_max': profile.entropy_max,
                'tile_table': profile.tile_table,
                'notes': profile.notes
            }

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
