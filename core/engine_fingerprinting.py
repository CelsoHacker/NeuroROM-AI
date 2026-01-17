# -*- coding: utf-8 -*-
"""
================================================================================
ENGINE FINGERPRINTING - Detecção Automática de Game Engines
================================================================================
Identifica automaticamente a engine/framework usado por um jogo:

PC Games:
- Unity (Unity3D)
- Unreal Engine (UE4/UE5)
- RPG Maker (MV/MZ/VX/XP)
- GameMaker Studio
- Godot
- Custom engines

ROMs:
- SNES: Tales engine, Lufia 2 engine, Square engine
- NES: Capcom engine, Konami VRC
- PS1: Square engine, Konami engine
- GBA: Pokemon engine, Fire Emblem engine

Usa: Assinaturas binárias, strings, estrutura de arquivos, padrões de memória
================================================================================
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class EngineType(Enum):
    """Tipos de engine detectados."""
    # PC Engines
    UNITY = "Unity"
    UNREAL = "Unreal Engine"
    RPG_MAKER_MV = "RPG Maker MV"
    RPG_MAKER_MZ = "RPG Maker MZ"
    RPG_MAKER_VX = "RPG Maker VX"
    RPG_MAKER_XP = "RPG Maker XP"
    GAMEMAKER = "GameMaker Studio"
    GODOT = "Godot"
    RENPY = "Ren'Py"
    CONSTRUCT = "Construct"

    # ROM Engines (SNES)
    SNES_TALES = "SNES Tales Engine"
    SNES_LUFIA2 = "SNES Lufia 2 Engine"
    SNES_SQUARE = "SNES Square Engine"
    SNES_QUINTET = "SNES Quintet Engine"
    SNES_CAPCOM = "SNES Capcom Engine"

    # ROM Engines (outros)
    NES_CAPCOM = "NES Capcom Engine"
    NES_KONAMI_VRC = "NES Konami VRC"
    PS1_SQUARE = "PS1 Square Engine"
    GBA_POKEMON = "GBA Pokemon Engine"
    GBA_FIRE_EMBLEM = "GBA Fire Emblem Engine"

    # Fallback
    CUSTOM = "Custom Engine"
    UNKNOWN = "Unknown"


@dataclass
class EngineFingerprintResult:
    """Resultado da detecção de engine."""
    engine: EngineType
    confidence: float  # 0.0 - 1.0
    version: Optional[str] = None
    signatures_found: List[str] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.signatures_found is None:
            self.signatures_found = []
        if self.metadata is None:
            self.metadata = {}


class EngineFingerprinter:
    """
    Detector universal de game engines.
    Funciona para PC games e ROMs.
    """

    # Assinaturas binárias de engines (bytes específicos)
    BINARY_SIGNATURES = {
        # Unity
        b'UnityEngine': EngineType.UNITY,
        b'Unity.': EngineType.UNITY,
        b'UnityPlayer.dll': EngineType.UNITY,
        b'globalgamemanagers': EngineType.UNITY,

        # Unreal
        b'UnrealEngine': EngineType.UNREAL,
        b'UE4Game': EngineType.UNREAL,
        b'/Script/Engine': EngineType.UNREAL,

        # RPG Maker
        b'RPG Maker MV': EngineType.RPG_MAKER_MV,
        b'RPG Maker MZ': EngineType.RPG_MAKER_MZ,
        b'RGSS': EngineType.RPG_MAKER_XP,  # Ruby Game Scripting System

        # GameMaker
        b'GameMaker': EngineType.GAMEMAKER,
        b'GM_': EngineType.GAMEMAKER,

        # Godot
        b'godot': EngineType.GODOT,
        b'GodotEngine': EngineType.GODOT,

        # Ren'Py
        b'renpy': EngineType.RENPY,
        b'Ren\'Py': EngineType.RENPY,
    }

    # Padrões de estrutura de arquivos/pastas
    FILE_STRUCTURE_SIGNATURES = {
        # Unity
        ('UnityPlayer.dll', 'Data'): EngineType.UNITY,
        ('*.assets', 'globalgamemanagers'): EngineType.UNITY,

        # Unreal
        ('*.pak', 'Engine'): EngineType.UNREAL,
        ('*.uasset', 'Content'): EngineType.UNREAL,

        # RPG Maker
        ('Game.exe', 'www', 'js'): EngineType.RPG_MAKER_MV,
        ('Game.exe', 'www', 'plugins'): EngineType.RPG_MAKER_MZ,
        ('Game.exe', 'Data', '*.rxdata'): EngineType.RPG_MAKER_XP,

        # GameMaker
        ('data.win', 'audiogroup*.dat'): EngineType.GAMEMAKER,

        # Godot
        ('*.pck', 'project.godot'): EngineType.GODOT,

        # Ren'Py
        ('renpy', 'game', 'script.rpy'): EngineType.RENPY,
    }

    # Assinaturas específicas de ROMs SNES
    ROM_SNES_SIGNATURES = {
        # Tales engine (Tales of Phantasia)
        b'\x20\x00\x5C\x00\x01\x00': ('tales_string_table', EngineType.SNES_TALES),

        # Lufia 2 (compressão LZSS específica)
        b'\x10\x00\xEE\x00': ('lufia2_compressed', EngineType.SNES_LUFIA2),

        # Square engine (FF6, Chrono Trigger)
        b'\xC2\x20\xA9\x00\x00\x8F': ('square_text_routine', EngineType.SNES_SQUARE),

        # Quintet (Terranigma, Soul Blazer)
        b'\x20\xE8\xFF\xC2\x30': ('quintet_init', EngineType.SNES_QUINTET),
    }

    def __init__(self, target_path: str):
        """
        Args:
            target_path: Caminho do jogo (pasta ou arquivo ROM)
        """
        self.target_path = Path(target_path)

        if not self.target_path.exists():
            raise FileNotFoundError(f"Target not found: {target_path}")

        self.is_rom = self.target_path.is_file()
        self.is_pc_game = self.target_path.is_dir()

    def detect(self) -> EngineFingerprintResult:
        """
        Detecta engine automaticamente.

        Returns:
            EngineFingerprintResult
        """
        if self.is_rom:
            return self._detect_rom_engine()
        elif self.is_pc_game:
            return self._detect_pc_engine()
        else:
            return EngineFingerprintResult(
                engine=EngineType.UNKNOWN,
                confidence=0.0,
                signatures_found=[]
            )

    def _detect_pc_engine(self) -> EngineFingerprintResult:
        """Detecta engine de jogo PC."""
        signatures_found = []
        engine_scores = {}  # {EngineType: score}

        # 1. Verifica estrutura de arquivos
        structure_result = self._check_file_structure()
        if structure_result:
            engine, confidence = structure_result
            signatures_found.append(f"file_structure: {engine.value}")
            engine_scores[engine] = engine_scores.get(engine, 0) + confidence

        # 2. Procura por DLLs/executáveis específicos
        binary_result = self._scan_pc_binaries()
        for engine, confidence in binary_result.items():
            signatures_found.append(f"binary: {engine.value}")
            engine_scores[engine] = engine_scores.get(engine, 0) + confidence

        # 3. Verifica arquivos de dados específicos
        data_result = self._check_pc_data_files()
        for engine, confidence in data_result.items():
            signatures_found.append(f"data_files: {engine.value}")
            engine_scores[engine] = engine_scores.get(engine, 0) + confidence

        # Escolhe engine com maior score
        if engine_scores:
            best_engine = max(engine_scores, key=engine_scores.get)
            confidence = min(engine_scores[best_engine] / 3.0, 1.0)  # Normaliza

            version = self._detect_engine_version(best_engine)

            return EngineFingerprintResult(
                engine=best_engine,
                confidence=confidence,
                version=version,
                signatures_found=signatures_found
            )

        return EngineFingerprintResult(
            engine=EngineType.CUSTOM,
            confidence=0.3,
            signatures_found=["No known engine detected"]
        )

    def _detect_rom_engine(self) -> EngineFingerprintResult:
        """Detecta engine de ROM."""
        signatures_found = []

        # Lê amostra da ROM
        with open(self.target_path, 'rb') as f:
            rom_data = f.read(1024 * 1024)  # Primeiros 1MB

        # Detecta plataforma primeiro
        platform = self._detect_rom_platform(rom_data)
        signatures_found.append(f"platform: {platform}")

        # Procura assinaturas específicas
        if platform == "SNES":
            for signature, (sig_name, engine) in self.ROM_SNES_SIGNATURES.items():
                if signature in rom_data:
                    signatures_found.append(f"snes_sig: {sig_name}")

                    return EngineFingerprintResult(
                        engine=engine,
                        confidence=0.85,
                        signatures_found=signatures_found,
                        metadata={'platform': platform}
                    )

        # Análise heurística baseada em padrões
        heuristic_result = self._rom_heuristic_analysis(rom_data, platform)

        return EngineFingerprintResult(
            engine=heuristic_result.get('engine', EngineType.CUSTOM),
            confidence=heuristic_result.get('confidence', 0.5),
            signatures_found=signatures_found + heuristic_result.get('signatures', []),
            metadata={'platform': platform}
        )

    def _check_file_structure(self) -> Optional[Tuple[EngineType, float]]:
        """Verifica estrutura de arquivos/pastas."""
        for pattern_tuple, engine in self.FILE_STRUCTURE_SIGNATURES.items():
            matches = 0

            for pattern in pattern_tuple:
                if self._pattern_exists(pattern):
                    matches += 1

            # Se encontrou a maioria dos padrões
            if matches / len(pattern_tuple) >= 0.6:
                confidence = matches / len(pattern_tuple)
                return (engine, confidence)

        return None

    def _pattern_exists(self, pattern: str) -> bool:
        """Verifica se padrão existe no diretório."""
        if '*' in pattern:
            # Glob pattern
            files = list(self.target_path.rglob(pattern))
            return len(files) > 0
        else:
            # Nome exato
            return (self.target_path / pattern).exists()

    def _scan_pc_binaries(self) -> Dict[EngineType, float]:
        """Escaneia binários (DLL/EXE) por assinaturas."""
        scores = {}

        # Procura DLLs e EXEs
        binaries = list(self.target_path.glob('*.dll'))
        binaries += list(self.target_path.glob('*.exe'))

        for binary in binaries[:20]:  # Limita a 20 arquivos
            try:
                with open(binary, 'rb') as f:
                    data = f.read(1024 * 512)  # 512KB sample

                # Procura assinaturas
                for signature, engine in self.BINARY_SIGNATURES.items():
                    if signature in data:
                        scores[engine] = scores.get(engine, 0) + 1.0

            except Exception:
                continue

        return scores

    def _check_pc_data_files(self) -> Dict[EngineType, float]:
        """Verifica arquivos de dados específicos."""
        scores = {}

        # Unity
        if (self.target_path / 'globalgamemanagers').exists():
            scores[EngineType.UNITY] = 1.0
        if list(self.target_path.glob('*.assets')):
            scores[EngineType.UNITY] = scores.get(EngineType.UNITY, 0) + 0.8

        # Unreal
        if list(self.target_path.rglob('*.pak')):
            scores[EngineType.UNREAL] = 1.0
        if list(self.target_path.rglob('*.uasset')):
            scores[EngineType.UNREAL] = scores.get(EngineType.UNREAL, 0) + 0.8

        # RPG Maker
        www_path = self.target_path / 'www'
        if www_path.exists():
            if (www_path / 'js').exists():
                scores[EngineType.RPG_MAKER_MV] = 1.0
            if (www_path / 'plugins').exists():
                scores[EngineType.RPG_MAKER_MZ] = 1.0

        # GameMaker
        if (self.target_path / 'data.win').exists():
            scores[EngineType.GAMEMAKER] = 1.0

        # Godot
        if (self.target_path / 'project.godot').exists():
            scores[EngineType.GODOT] = 1.0
        if list(self.target_path.glob('*.pck')):
            scores[EngineType.GODOT] = scores.get(EngineType.GODOT, 0) + 0.8

        return scores

    def _detect_engine_version(self, engine: EngineType) -> Optional[str]:
        """Tenta detectar versão da engine."""
        # Unity - verifica globalgamemanagers
        if engine == EngineType.UNITY:
            ggm_path = self.target_path / 'globalgamemanagers'
            if ggm_path.exists():
                try:
                    with open(ggm_path, 'rb') as f:
                        data = f.read(1024)

                    # Procura string de versão
                    version_match = re.search(b'(\d+\.\d+\.\d+)', data)
                    if version_match:
                        return version_match.group(1).decode('ascii')
                except:
                    pass

        # RPG Maker - verifica package.json
        if engine in [EngineType.RPG_MAKER_MV, EngineType.RPG_MAKER_MZ]:
            package_json = self.target_path / 'www' / 'package.json'
            if package_json.exists():
                try:
                    import json
                    with open(package_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return data.get('version', None)
                except:
                    pass

        return None

    def _detect_rom_platform(self, data: bytes) -> str:
        """Detecta plataforma da ROM."""
        # SNES - header em 0x7FC0 ou 0xFFC0
        if len(data) >= 0x10000:
            # LoROM header
            if data[0x7FDC:0x7FDE] == b'\xAA\x55':
                return "SNES"
            # HiROM header
            if data[0xFFDC:0xFFDE] == b'\xAA\x55':
                return "SNES"

        # NES - "NES\x1A" header
        if data.startswith(b'NES\x1A'):
            return "NES"

        # GBA - Nintendo logo
        if data[0x04:0x9C] == bytes.fromhex('24FFAE51699AA2213D84820A84E40940'):
            return "GBA"

        # PS1 - "PLAYSTATION" string
        if b'PLAYSTATION' in data[:0x10000]:
            return "PS1"

        return "Unknown"

    def _rom_heuristic_analysis(self, data: bytes, platform: str) -> Dict:
        """Análise heurística de ROM."""
        result = {
            'engine': EngineType.CUSTOM,
            'confidence': 0.5,
            'signatures': []
        }

        if platform == "SNES":
            # Verifica padrões comuns de engines Square
            if b'\x20\xE8' in data and b'\xC2\x30' in data:
                result['signatures'].append('square_common_pattern')
                result['engine'] = EngineType.SNES_SQUARE
                result['confidence'] = 0.65

            # Verifica padrões Quintet
            if data.count(b'\x20\xE8\xFF') > 5:
                result['signatures'].append('quintet_call_pattern')
                result['engine'] = EngineType.SNES_QUINTET
                result['confidence'] = 0.6

        elif platform == "PS1":
            # Square PS1 (Final Fantasy VII-IX)
            if b'SQUARE' in data or b'SQUARESOFT' in data:
                result['signatures'].append('square_copyright')
                result['engine'] = EngineType.PS1_SQUARE
                result['confidence'] = 0.7

        elif platform == "GBA":
            # Pokemon engine
            if b'POKEMON' in data:
                result['signatures'].append('pokemon_string')
                result['engine'] = EngineType.GBA_POKEMON
                result['confidence'] = 0.8

        return result


def detect_engine(target_path: str) -> EngineFingerprintResult:
    """
    Função de conveniência para detecção rápida.

    Args:
        target_path: Caminho do jogo ou ROM

    Returns:
        EngineFingerprintResult
    """
    fingerprinter = EngineFingerprinter(target_path)
    return fingerprinter.detect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python engine_fingerprinting.py <game_path_or_rom>")
        print("\nExample:")
        print('  python engine_fingerprinting.py "C:\\Games\\MyGame"')
        print('  python engine_fingerprinting.py "ROMs/game.smc"')
        sys.exit(1)

    target = sys.argv[1]
    result = detect_engine(target)

    print(f"\n🔍 ENGINE FINGERPRINTING RESULT")
    print(f"{'='*70}")
    print(f"Target: {target}")
    print(f"Engine: {result.engine.value}")
    print(f"Confidence: {result.confidence * 100:.1f}%")

    if result.version:
        print(f"Version: {result.version}")

    if result.signatures_found:
        print(f"\nSignatures detected:")
        for sig in result.signatures_found:
            print(f"  - {sig}")

    if result.metadata:
        print(f"\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    print(f"{'='*70}\n")
