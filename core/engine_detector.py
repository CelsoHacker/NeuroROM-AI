# -*- coding: utf-8 -*-
"""
Engine Detector - Detecta automaticamente o tipo de jogo/ROM
Identifica: Console ROMs, Unity, Unreal, Godot, Doom, Quake, etc.
"""

import os
import struct
import zipfile
from pathlib import Path
from typing import Dict, Optional, List


class EngineDetector:
    """Detecta automaticamente o engine/tipo de jogo ou ROM."""

    # Extensões de ROMs de console
    ROM_EXTENSIONS = {
        '.smc': 'SNES ROM',
        '.sfc': 'SNES ROM',
        '.nes': 'NES ROM',
        '.gb': 'Game Boy ROM',
        '.gbc': 'Game Boy Color ROM',
        '.gba': 'Game Boy Advance ROM',
        '.z64': 'Nintendo 64 ROM',
        '.n64': 'Nintendo 64 ROM',
        '.nds': 'Nintendo DS ROM',
        '.bin': 'PlayStation/Genesis ROM',
        '.iso': 'CD-ROM (PS1/PS2/GameCube/etc)',
        '.gcm': 'GameCube ROM',
        '.wbfs': 'Wii ROM',
    }

    # Extensões de jogos de PC
    PC_EXTENSIONS = {
        '.exe': 'PC Executable',
        '.wad': 'Doom WAD',
        '.pak': 'PAK Archive (Quake/Unreal)',
        '.dat': 'Generic Data File',
        '.assets': 'Unity Assets',
        '.unity3d': 'Unity Asset Bundle',
        '.json': 'JSON Data (RPG Maker/RenPy)',
        '.rpy': 'RenPy Script',
        '.txt': 'Text File',
    }

    def __init__(self):
        self.detection_result: Optional[Dict] = None

    def detect(self, file_path: str) -> Dict:
        """
        Detecta o tipo de arquivo/engine.

        Returns:
            Dict com informações:
            {
                'type': 'ROM' | 'PC_GAME',
                'platform': 'SNES' | 'Unity' | 'Doom' | etc,
                'extension': '.smc',
                'engine': 'Console' | 'Unity' | 'Unreal' | 'Doom' | etc,
                'converter_needed': True/False,
                'converter_suggestion': 'converter_zdoom_simples.py' | None,
                'tabs_supported': [1, 2, 3] | [1, 2],
                'notes': 'Informações adicionais'
            }
        """

        if not os.path.exists(file_path):
            return self._error_result(f"Arquivo não encontrado: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        file_size = os.path.getsize(file_path)

        # 1. Detectar ROM de console
        if ext in self.ROM_EXTENSIONS:
            return self._detect_rom(file_path, ext, file_size)

        # 2. Detectar jogo de PC específico
        if ext in self.PC_EXTENSIONS:
            return self._detect_pc_game(file_path, ext, file_size)

        # 3. Tentar detectar pelo conteúdo (sem extensão clara)
        return self._detect_by_content(file_path)

    def _detect_rom(self, file_path: str, ext: str, file_size: int) -> Dict:
        """Detecta ROM de console."""

        platform = self.ROM_EXTENSIONS.get(ext, 'Unknown ROM')

        # Validação específica por console
        is_valid = True
        notes = []

        if ext in ['.smc', '.sfc']:
            # SNES: múltiplo de 1024 bytes (com ou sem header)
            is_valid = file_size % 1024 == 0 or (file_size - 512) % 1024 == 0
            if file_size > 6 * 1024 * 1024:
                notes.append("ROM grande - pode demorar mais para traduzir")

        elif ext == '.nes':
            # NES: header "NES\x1a"
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(4)
                    is_valid = header == b'NES\x1a'
            except:
                is_valid = False

        elif ext in ['.gba']:
            # GBA: ~4-32 MB
            is_valid = 1 * 1024 * 1024 <= file_size <= 32 * 1024 * 1024

        return {
            'type': 'ROM',
            'platform': platform,
            'extension': ext,
            'engine': 'Console',
            'valid': is_valid,
            'converter_needed': False,
            'converter_suggestion': None,
            'tabs_supported': [1, 2, 3],  # Todas as 3 abas funcionam
            'reinsertion_supported': True,
            'graphics_lab_supported': True,
            'notes': ' | '.join(notes) if notes else 'ROM de console - processo completo automático (3 abas)'
        }

    def _detect_pc_game(self, file_path: str, ext: str, file_size: int) -> Dict:
        """Detecta jogo de PC e identifica engine."""

        engine = 'Unknown'
        converter_suggestion = None
        notes = []

        # Doom WAD
        if ext == '.wad':
            engine = 'Doom/Heretic/Hexen'
            converter_suggestion = 'converter_zdoom_simples.py'

            # Verificar se é WAD válido
            try:
                with open(file_path, 'rb') as f:
                    magic = f.read(4)
                    valid = magic in [b'IWAD', b'PWAD']
                    if valid:
                        notes.append("WAD válido detectado")
                    else:
                        notes.append("Arquivo .wad mas header inválido")
            except:
                pass

        # Quake PAK
        elif ext == '.pak':
            engine = 'Quake/Half-Life'
            converter_suggestion = 'converter_quake.py (em desenvolvimento)'

            try:
                with open(file_path, 'rb') as f:
                    magic = f.read(4)
                    if magic == b'PACK':
                        notes.append("Quake PAK detectado")
                        engine = 'Quake'
            except:
                pass

        # Unity
        elif ext in ['.assets', '.unity3d']:
            engine = 'Unity'
            notes.append("Use UABE (Unity Assets Bundle Extractor) + processo manual")
            notes.append("Veja: MANUAL_JOGOS_PC.md - Seção Unity")

        # Unreal
        elif ext == '.pak' and self._is_unreal_pak(file_path):
            engine = 'Unreal Engine'
            notes.append("Use UnrealPak + processo manual")

        # RPG Maker
        elif ext == '.json' and self._is_rpgmaker(file_path):
            engine = 'RPG Maker MV/MZ'
            notes.append("Arquivos JSON - edite diretamente após tradução")

        # RenPy
        elif ext == '.rpy':
            engine = 'RenPy (Visual Novel)'
            notes.append("Scripts RenPy - edite após tradução")

        # Executável genérico
        elif ext == '.exe':
            engine = self._detect_exe_engine(file_path)
            notes.append("Executável detectado - extraia textos primeiro")

        return {
            'type': 'PC_GAME',
            'platform': self.PC_EXTENSIONS.get(ext, 'PC Game'),
            'extension': ext,
            'engine': engine,
            'valid': True,
            'converter_needed': True,
            'converter_suggestion': converter_suggestion,
            'tabs_supported': [1, 2],  # Apenas extração e tradução
            'reinsertion_supported': False,
            'graphics_lab_supported': False,
            'notes': ' | '.join(notes) if notes else 'Jogo de PC - use conversor após tradução'
        }

    def _detect_by_content(self, file_path: str) -> Dict:
        """Detecta tipo analisando o conteúdo do arquivo."""

        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)

            # Doom WAD (sem extensão)
            if header[:4] in [b'IWAD', b'PWAD']:
                return {
                    'type': 'PC_GAME',
                    'platform': 'Doom WAD',
                    'extension': '.wad',
                    'engine': 'Doom',
                    'valid': True,
                    'converter_needed': True,
                    'converter_suggestion': 'converter_zdoom_simples.py',
                    'tabs_supported': [1, 2],
                    'reinsertion_supported': False,
                    'graphics_lab_supported': False,
                    'notes': 'WAD detectado pelo header - renomeie para .wad'
                }

            # NES ROM (sem extensão)
            if header[:4] == b'NES\x1a':
                return {
                    'type': 'ROM',
                    'platform': 'NES ROM',
                    'extension': '.nes',
                    'engine': 'Console',
                    'valid': True,
                    'converter_needed': False,
                    'converter_suggestion': None,
                    'tabs_supported': [1, 2, 3],
                    'reinsertion_supported': True,
                    'graphics_lab_supported': True,
                    'notes': 'NES ROM detectada - renomeie para .nes'
                }

            # ZIP (pode ser Unity, APK, etc)
            if header[:4] == b'PK\x03\x04':
                return self._detect_zip_content(file_path)

        except Exception as e:
            pass

        return {
            'type': 'UNKNOWN',
            'platform': 'Unknown',
            'extension': os.path.splitext(file_path)[1],
            'engine': 'Unknown',
            'valid': False,
            'converter_needed': False,
            'converter_suggestion': None,
            'tabs_supported': [1, 2],  # Tentar extrair mesmo assim
            'reinsertion_supported': False,
            'graphics_lab_supported': False,
            'notes': 'Tipo não identificado - tente extrair textos manualmente'
        }

    def _detect_zip_content(self, file_path: str) -> Dict:
        """Detecta conteúdo de arquivo ZIP (Unity, APK, etc)."""

        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                files = z.namelist()

                # Unity Asset Bundle
                if any('unity3d' in f.lower() or 'assets' in f.lower() for f in files):
                    return {
                        'type': 'PC_GAME',
                        'platform': 'Unity Asset Bundle',
                        'extension': '.zip',
                        'engine': 'Unity',
                        'valid': True,
                        'converter_needed': True,
                        'converter_suggestion': None,
                        'tabs_supported': [1, 2],
                        'reinsertion_supported': False,
                        'graphics_lab_supported': False,
                        'notes': 'Unity asset bundle - use UABE para extrair'
                    }

                # APK Android
                if 'AndroidManifest.xml' in files:
                    return {
                        'type': 'PC_GAME',
                        'platform': 'Android APK',
                        'extension': '.apk',
                        'engine': 'Android',
                        'valid': True,
                        'converter_needed': True,
                        'converter_suggestion': None,
                        'tabs_supported': [1, 2],
                        'reinsertion_supported': False,
                        'graphics_lab_supported': False,
                        'notes': 'APK Android - descompacte e analise recursos'
                    }
        except:
            pass

        return self._error_result("ZIP genérico - conteúdo desconhecido")

    def _is_unreal_pak(self, file_path: str) -> bool:
        """Verifica se é arquivo PAK do Unreal Engine."""
        try:
            with open(file_path, 'rb') as f:
                # PAK do Unreal tem magic number no final do arquivo
                f.seek(-44, 2)  # 44 bytes do final
                footer = f.read(44)
                # Verifica magic "0x5A6F12E1"
                return footer[-4:] == b'\xe1\x12\x6f\x5a'
        except:
            return False

    def _is_rpgmaker(self, file_path: str) -> bool:
        """Verifica se é arquivo JSON do RPG Maker."""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # RPG Maker tem estruturas específicas
                return any(key in data for key in ['actors', 'items', 'weapons', 'skills'])
        except:
            return False

    def _detect_exe_engine(self, file_path: str) -> str:
        """Tenta detectar engine de um executável."""

        try:
            with open(file_path, 'rb') as f:
                content = f.read(1024 * 100)  # Primeiros 100KB
                content_str = content.decode('latin-1', errors='ignore').lower()

                # Unity
                if 'unity' in content_str or 'unityengine' in content_str:
                    return 'Unity'

                # Unreal
                if 'unreal' in content_str or 'unrealengine' in content_str:
                    return 'Unreal Engine'

                # Godot
                if 'godot' in content_str:
                    return 'Godot'

                # RPG Maker
                if 'rpg maker' in content_str or 'rgss' in content_str:
                    return 'RPG Maker'

                # Game Maker
                if 'gamemaker' in content_str or 'yoyogames' in content_str:
                    return 'Game Maker'

                # RenPy
                if 'renpy' in content_str:
                    return 'RenPy'
        except:
            pass

        return 'Unknown Engine'

    def _error_result(self, message: str) -> Dict:
        """Retorna resultado de erro."""
        return {
            'type': 'ERROR',
            'platform': 'Unknown',
            'extension': '',
            'engine': 'Unknown',
            'valid': False,
            'converter_needed': False,
            'converter_suggestion': None,
            'tabs_supported': [],
            'reinsertion_supported': False,
            'graphics_lab_supported': False,
            'notes': message
        }

    def get_recommended_workflow(self, detection: Dict) -> List[str]:
        """
        Retorna workflow recomendado baseado na detecção.

        Returns:
            Lista de passos sugeridos
        """

        workflow = []

        if detection['type'] == 'ROM':
            workflow.append("1. Aba 'Extração' - Extrair textos da ROM")
            workflow.append("2. Aba 'Tradução' - Traduzir textos com IA")
            workflow.append("3. Aba 'Reinserção' - Reinserir textos na ROM")
            workflow.append("4. (Opcional) Lab Gráfico - Traduzir textos em imagens")
            workflow.append("✅ Processo completo automático!")

        elif detection['type'] == 'PC_GAME':
            workflow.append("1. Aba 'Extração' - Extrair textos do jogo")
            workflow.append("2. Aba 'Tradução' - Traduzir textos com IA")

            if detection['converter_suggestion']:
                workflow.append(f"3. Executar conversor: {detection['converter_suggestion']}")
                workflow.append("4. Instalar tradução no jogo (veja manual)")
            else:
                workflow.append("3. ⚠️ Processo manual necessário")
                workflow.append("4. Veja: MANUAL_JOGOS_PC.md para instruções")

            workflow.append("")
            workflow.append("❌ Aba 'Reinserção' NÃO funciona para jogos de PC!")
            workflow.append("❌ Lab Gráfico disponível apenas para ROMs de console")

        else:
            workflow.append("⚠️ Tipo de arquivo não reconhecido")
            workflow.append("1. Tente extrair textos (Aba 'Extração')")
            workflow.append("2. Se funcionar, traduza (Aba 'Tradução')")
            workflow.append("3. Reinserção será manual")

        return workflow


# Função de conveniência
def detect_game_engine(file_path: str) -> Dict:
    """
    Detecta automaticamente o engine/tipo de um jogo ou ROM.

    Args:
        file_path: Caminho do arquivo

    Returns:
        Dicionário com informações de detecção
    """
    detector = EngineDetector()
    return detector.detect(file_path)


# Teste
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Uso: python engine_detector.py <arquivo>")
        sys.exit(1)

    result = detect_game_engine(sys.argv[1])

    print("\n" + "="*60)
    print("🔍 DETECÇÃO DE ENGINE")
    print("="*60)
    print(f"Tipo: {result['type']}")
    print(f"Plataforma: {result['platform']}")
    print(f"Engine: {result['engine']}")
    print(f"Extensão: {result['extension']}")
    print(f"Válido: {'✅' if result['valid'] else '❌'}")
    print(f"\nAbas suportadas: {result['tabs_supported']}")
    print(f"Reinserção automática: {'✅' if result['reinsertion_supported'] else '❌'}")
    print(f"Lab Gráfico: {'✅' if result['graphics_lab_supported'] else '❌'}")

    if result['converter_suggestion']:
        print(f"\n💡 Conversor sugerido: {result['converter_suggestion']}")

    print(f"\n📝 Notas: {result['notes']}")

    # Workflow
    detector = EngineDetector()
    workflow = detector.get_recommended_workflow(result)

    print("\n" + "="*60)
    print("📋 WORKFLOW RECOMENDADO")
    print("="*60)
    for step in workflow:
        print(step)
    print("="*60 + "\n")
