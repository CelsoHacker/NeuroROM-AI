# -*- coding: utf-8 -*-
"""
================================================================================
PC GAME SCANNER - Varredura Automática de Pastas de Jogos
================================================================================
Varre diretório de jogo PC e identifica automaticamente arquivos com texto:
- Arquivos textuais comuns (.txt, .json, .xml, .ini, .cfg)
- Scripts (.lua, .js, .py, .rb, .cs)
- Formatos proprietários (.dat, .bin com texto)
- Localização de pastas (lang/, localization/, text/)

NÃO usa profiles hardcoded - análise puramente heurística
================================================================================
"""

import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict
import re


class GameFile:
    """Representa um arquivo encontrado no jogo."""

    def __init__(self, path: Path, game_root: Path):
        self.path = path
        self.relative_path = path.relative_to(game_root)
        self.name = path.name
        self.extension = path.suffix.lower()
        self.size = path.stat().st_size
        self.category = "unknown"
        self.priority = 0
        self.has_text = False
        self.encoding_hint = None
        self.is_localization_file = False

    def __repr__(self):
        return f"<GameFile {self.relative_path} ({self.category}) priority={self.priority}>"


class PCGameScanner:
    """
    Scanner universal de jogos de PC.
    Identifica arquivos traduzíveis sem conhecimento prévio do jogo.
    """

    # Extensões conhecidas por categoria
    TEXT_EXTENSIONS = {
        # Texto puro
        '.txt', '.text', '.md', '.readme',

        # Configuração
        '.ini', '.cfg', '.config', '.conf', '.properties',

        # Dados estruturados
        '.json', '.xml', '.yaml', '.yml', '.toml',

        # Scripts
        '.lua', '.js', '.py', '.rb', '.cs', '.gd', '.nut',
        '.as', '.ash', '.coffee',

        # Localização específica
        '.lang', '.locale', '.translation', '.i18n', '.po', '.pot',

        # Bancos de dados leves
        '.csv', '.tsv', '.sql',

        # Web/HTML
        '.html', '.htm', '.css',

        # Outros textuais
        '.log', '.manifest', '.srt', '.sub'
    }

    # Extensões binárias que PODEM conter texto
    BINARY_TEXT_CANDIDATES = {
        '.dat', '.bin', '.pak', '.res', '.resource', '.assets',
        '.bundle', '.archive', '.data', '.db', '.unity3d'
    }

    # Padrões de nomes de arquivos de localização
    LOCALIZATION_PATTERNS = [
        re.compile(r'lang', re.IGNORECASE),
        re.compile(r'local', re.IGNORECASE),
        re.compile(r'translation', re.IGNORECASE),
        re.compile(r'text', re.IGNORECASE),
        re.compile(r'string', re.IGNORECASE),
        re.compile(r'dialog', re.IGNORECASE),
        re.compile(r'message', re.IGNORECASE),
        re.compile(r'i18n', re.IGNORECASE),
        re.compile(r'l10n', re.IGNORECASE),
        re.compile(r'en\.', re.IGNORECASE),  # english.txt, en.json, etc
        re.compile(r'_en[_\.]', re.IGNORECASE),  # file_en.txt
    ]

    # Padrões de pastas de localização
    LOCALIZATION_FOLDERS = [
        'lang', 'language', 'languages',
        'locale', 'locales', 'localization',
        'text', 'texts',
        'strings', 'string',
        'dialog', 'dialogs', 'dialogue',
        'data/text', 'data/strings',
        'resources/text', 'resources/lang',
        'assets/text', 'assets/localization',
        'i18n', 'l10n',
        'english', 'en', 'en-us', 'en_us'
    ]

    # Arquivos a ignorar (binários de sistema, executáveis, etc)
    IGNORE_EXTENSIONS = {
        '.exe', '.dll', '.so', '.dylib', '.a',
        '.obj', '.o', '.lib',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.mp3', '.wav', '.ogg', '.flac',
        '.mp4', '.avi', '.mkv', '.webm',
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tga', '.dds',
        '.ttf', '.otf', '.fon',
        '.pdb', '.idb', '.pch'
    }

    def __init__(self, game_path: str, max_depth: int = 10):
        """
        Args:
            game_path: Caminho raiz do jogo
            max_depth: Profundidade máxima de varredura (evita loops)
        """
        self.game_path = Path(game_path)
        self.max_depth = max_depth
        self.files: List[GameFile] = []
        self.stats = defaultdict(int)

        if not self.game_path.exists():
            raise FileNotFoundError(f"Game path not found: {game_path}")

    def scan(self) -> List[GameFile]:
        """
        Executa varredura completa do diretório do jogo.

        Returns:
            Lista de GameFile ordenada por prioridade
        """
        print(f"\n🎮 PC GAME SCANNER - Automatic File Detection")
        print(f"{'='*70}")
        print(f"Scanning: {self.game_path}")
        print(f"{'='*70}\n")

        # Varre recursivamente
        self._scan_directory(self.game_path, depth=0)

        # Analisa arquivos encontrados
        self._analyze_files()

        # Ordena por prioridade (maior primeiro)
        self.files.sort(key=lambda f: f.priority, reverse=True)

        self._print_summary()

        return self.files

    def _scan_directory(self, directory: Path, depth: int):
        """Varre diretório recursivamente."""
        if depth > self.max_depth:
            return

        try:
            for item in directory.iterdir():
                # Pula arquivos/pastas ocultos
                if item.name.startswith('.'):
                    continue

                if item.is_file():
                    self._process_file(item)
                elif item.is_dir():
                    # Varre subdiretório
                    self._scan_directory(item, depth + 1)

        except PermissionError:
            print(f"⚠️  Permission denied: {directory}")
            pass

    def _process_file(self, file_path: Path):
        """Processa arquivo individual."""
        # Ignora extensões conhecidamente inúteis
        if file_path.suffix.lower() in self.IGNORE_EXTENSIONS:
            self.stats['ignored'] += 1
            return

        # Ignora arquivos muito grandes (>100MB provavelmente não é texto)
        try:
            size = file_path.stat().st_size
            if size > 100 * 1024 * 1024:  # 100MB
                self.stats['too_large'] += 1
                return
        except:
            return

        # Cria objeto GameFile
        game_file = GameFile(file_path, self.game_path)

        # Categoriza
        self._categorize_file(game_file)

        # Adiciona à lista
        self.files.append(game_file)
        self.stats['total_files'] += 1

    def _categorize_file(self, game_file: GameFile):
        """Categoriza arquivo e calcula prioridade."""
        ext = game_file.extension

        # Categoria 1: Arquivos de texto conhecidos
        if ext in self.TEXT_EXTENSIONS:
            game_file.category = "text"
            game_file.has_text = True
            game_file.priority = 50

            # Bonus: se nome sugere localização
            if self._is_localization_file(game_file.relative_path):
                game_file.is_localization_file = True
                game_file.priority += 30

        # Categoria 2: Binários que podem conter texto
        elif ext in self.BINARY_TEXT_CANDIDATES:
            game_file.category = "binary_text_candidate"
            game_file.priority = 20

            # Verifica se está em pasta de localização
            if self._is_in_localization_folder(game_file.relative_path):
                game_file.priority += 20
                game_file.is_localization_file = True

        # Categoria 3: Sem extensão (pode ser texto)
        elif not ext:
            game_file.category = "no_extension"
            game_file.priority = 10

        # Categoria 4: Extensão desconhecida
        else:
            game_file.category = "unknown"
            game_file.priority = 5

    def _is_localization_file(self, path: Path) -> bool:
        """Verifica se arquivo parece ser de localização pelo nome."""
        path_str = str(path).lower()

        for pattern in self.LOCALIZATION_PATTERNS:
            if pattern.search(path_str):
                return True

        return False

    def _is_in_localization_folder(self, path: Path) -> bool:
        """Verifica se arquivo está em pasta de localização."""
        path_parts = [p.lower() for p in path.parts]

        for folder_pattern in self.LOCALIZATION_FOLDERS:
            folder_parts = folder_pattern.lower().split('/')

            # Verifica se todos os componentes do padrão aparecem no caminho
            if all(part in path_parts for part in folder_parts):
                return True

        return False

    def _analyze_files(self):
        """Análise adicional dos arquivos encontrados."""
        for game_file in self.files:
            # Se é arquivo de texto, tenta detectar encoding
            if game_file.category == "text":
                game_file.encoding_hint = self._detect_encoding_hint(game_file.path)

            # Se é binário candidato, verifica se realmente tem texto
            elif game_file.category == "binary_text_candidate":
                if self._binary_has_text(game_file.path):
                    game_file.has_text = True
                    game_file.priority += 10

    def _detect_encoding_hint(self, file_path: Path) -> Optional[str]:
        """
        Tenta detectar encoding lendo início do arquivo.

        Returns:
            Hint de encoding ('utf-8', 'utf-16', 'latin-1', etc) ou None
        """
        try:
            # Lê primeiros 4KB
            with open(file_path, 'rb') as f:
                sample = f.read(4096)

            # Detecta BOM (Byte Order Mark)
            if sample.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
            elif sample.startswith(b'\xff\xfe'):
                return 'utf-16-le'
            elif sample.startswith(b'\xfe\xff'):
                return 'utf-16-be'

            # Tenta decodificar como UTF-8
            try:
                sample.decode('utf-8')
                return 'utf-8'
            except UnicodeDecodeError:
                pass

            # Tenta latin-1 (sempre funciona, mas pode não ser correto)
            try:
                sample.decode('latin-1')
                # Se tem caracteres acentuados, pode ser latin-1 ou windows-1252
                if any(b in sample for b in range(0x80, 0xFF)):
                    return 'windows-1252'
            except:
                pass

            return None

        except Exception:
            return None

    def _binary_has_text(self, file_path: Path, sample_size: int = 8192) -> bool:
        """
        Verifica se arquivo binário contém texto legível.

        Heurística: Se > 30% dos bytes são ASCII imprimível, provavelmente tem texto.
        """
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(sample_size)

            if not sample:
                return False

            # Conta bytes ASCII imprimíveis
            printable_count = sum(1 for b in sample if 0x20 <= b <= 0x7E or b in {0x09, 0x0A, 0x0D})

            ratio = printable_count / len(sample)

            return ratio > 0.3

        except Exception:
            return False

    def _print_summary(self):
        """Exibe resumo da varredura."""
        print(f"\n📊 SCAN SUMMARY")
        print(f"{'='*70}")
        print(f"Total files scanned: {self.stats['total_files']}")
        print(f"Ignored (binary/media): {self.stats['ignored']}")
        print(f"Too large (>100MB): {self.stats['too_large']}")

        # Agrupa por categoria
        by_category = defaultdict(int)
        text_files = 0
        localization_files = 0

        for f in self.files:
            by_category[f.category] += 1
            if f.has_text:
                text_files += 1
            if f.is_localization_file:
                localization_files += 1

        print(f"\nFILES BY CATEGORY:")
        for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            print(f"  {category:25s}: {count:4d}")

        print(f"\nTRANSLATABLE FILES:")
        print(f"  Files with text: {text_files}")
        print(f"  Localization files: {localization_files}")

        # Top 10 arquivos por prioridade
        print(f"\nTOP 10 HIGH-PRIORITY FILES:")
        for i, f in enumerate(self.files[:10], 1):
            loc_marker = "🌍" if f.is_localization_file else "  "
            print(f"  {i:2d}. {loc_marker} [{f.priority:3d}] {f.relative_path}")

        print(f"\n{'='*70}\n")

    def export_file_list(self, output_path: str):
        """Exporta lista de arquivos para JSON."""
        import json
        from datetime import datetime

        export_data = {
            'scan_timestamp': datetime.now().isoformat(),
            'game_path': str(self.game_path),
            'total_files': len(self.files),
            'stats': dict(self.stats),
            'files': [
                {
                    'path': str(f.relative_path),
                    'category': f.category,
                    'priority': f.priority,
                    'size': f.size,
                    'has_text': f.has_text,
                    'is_localization': f.is_localization_file,
                    'encoding_hint': f.encoding_hint
                }
                for f in self.files
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(export_data, file, indent=2, ensure_ascii=False)

        print(f"✅ File list exported to: {output_path}")

    def get_translatable_files(self, min_priority: int = 20) -> List[GameFile]:
        """
        Retorna apenas arquivos traduzíveis acima de prioridade mínima.

        Args:
            min_priority: Prioridade mínima (default: 20)

        Returns:
            Lista filtrada de GameFile
        """
        return [f for f in self.files if f.priority >= min_priority and f.has_text]


def scan_game_directory(game_path: str, export_json: bool = True) -> PCGameScanner:
    """
    Função de conveniência para scan direto.

    Args:
        game_path: Caminho do diretório do jogo
        export_json: Se True, exporta lista de arquivos

    Returns:
        PCGameScanner com resultados
    """
    scanner = PCGameScanner(game_path)
    scanner.scan()

    if export_json:
        output_path = Path(game_path) / 'game_files_scan.json'
        scanner.export_file_list(str(output_path))

    return scanner


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pc_game_scanner.py <game_directory>")
        print("\nExample:")
        print('  python pc_game_scanner.py "C:\\Games\\MyGame"')
        sys.exit(1)

    game_dir = sys.argv[1]
    scanner = scan_game_directory(game_dir, export_json=True)

    # Exibe arquivos traduzíveis
    translatable = scanner.get_translatable_files(min_priority=30)
    print(f"\n🎯 RECOMMENDED FOR TRANSLATION ({len(translatable)} files):")
    for f in translatable[:20]:  # Top 20
        print(f"  {f.relative_path}")
