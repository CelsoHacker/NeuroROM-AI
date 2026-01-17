# -*- coding: utf-8 -*-
"""
================================================================================
PC TEXT EXTRACTOR - Extração Universal de Textos de Jogos de PC
================================================================================
Extrai textos traduzíveis de jogos de PC preservando estrutura e formatação:
- JSON: Extrai valores de strings, preserva hierarquia
- XML: Extrai conteúdo de tags, preserva estrutura
- INI: Extrai valores, preserva seções
- Lua/Script: Extrai strings literais
- Plain text: Extrai linhas não vazias

NÃO assume formato específico - usa detecção automática
================================================================================
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Importa módulos existentes
from .pc_game_scanner import PCGameScanner, GameFile
from .file_format_detector import FileFormatDetector, FileFormat, FormatStructure
from .encoding_detector import EncodingDetector, EncodingResult


@dataclass
class ExtractedText:
    """Representa um texto extraído com metadados completos."""
    id: int
    file_path: str
    line_number: Optional[int]
    context: str  # JSON path, XML xpath, seção INI, etc
    original_text: str
    encoding: str
    format: str
    extractable: bool = True  # Se pode ser traduzido
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict:
        """Converte para dicionário (para JSON)."""
        return asdict(self)


class PCTextExtractor:
    """
    Extrator universal de textos de jogos de PC.
    Funciona sem conhecimento prévio do jogo.
    """

    # Padrões para identificar texto não-traduzível
    NON_TRANSLATABLE_PATTERNS = [
        re.compile(r'^[\d\s\.\,\:\;\-\_\=\+\*\/\(\)\[\]\{\}]+$'),  # Apenas números/símbolos
        re.compile(r'^[a-zA-Z0-9_\-\.]+\.(png|jpg|jpeg|gif|bmp|wav|mp3|ogg)$', re.I),  # Caminhos de arquivos
        re.compile(r'^#[0-9a-fA-F]{6}$'),  # Cores hex
        re.compile(r'^https?://'),  # URLs
        re.compile(r'^[a-zA-Z]:\\'),  # Caminhos Windows
        re.compile(r'^/[a-zA-Z]'),  # Caminhos Unix
    ]

    # Tamanho mínimo de texto para ser considerado traduzível
    MIN_TEXT_LENGTH = 2

    def __init__(self, game_path: str):
        """
        Args:
            game_path: Caminho raiz do jogo
        """
        self.game_path = Path(game_path)
        self.extracted_texts: List[ExtractedText] = []
        self.next_id = 1

        if not self.game_path.exists():
            raise FileNotFoundError(f"Game path not found: {game_path}")

    def extract_all(self, min_priority: int = 30) -> List[ExtractedText]:
        """
        Extrai textos de todos os arquivos relevantes do jogo.

        Args:
            min_priority: Prioridade mínima de arquivo (ver PCGameScanner)

        Returns:
            Lista de ExtractedText
        """
        print(f"\n📝 PC TEXT EXTRACTOR - Universal Text Extraction")
        print(f"{'='*70}")
        print(f"Game: {self.game_path}")
        print(f"{'='*70}\n")

        # 1. Scan: Encontra arquivos traduzíveis
        print(f"[1/3] 🔍 Scanning for translatable files...")
        scanner = PCGameScanner(str(self.game_path))
        scanner.scan()

        translatable_files = scanner.get_translatable_files(min_priority=min_priority)

        print(f"✅ Found {len(translatable_files)} high-priority files\n")

        # 2. Extract: Processa cada arquivo
        print(f"[2/3] 📄 Extracting texts from files...")

        for game_file in translatable_files:
            self._extract_from_file(game_file)

        print(f"\n✅ Extraction completed: {len(self.extracted_texts)} texts extracted\n")

        # 3. Filter: Remove textos não traduzíveis
        print(f"[3/3] 🔍 Filtering non-translatable texts...")
        self._filter_non_translatable()

        translatable_count = sum(1 for t in self.extracted_texts if t.extractable)
        print(f"✅ Translatable texts: {translatable_count}/{len(self.extracted_texts)}\n")

        return self.extracted_texts

    def _extract_from_file(self, game_file: GameFile):
        """Extrai textos de um arquivo individual."""
        file_path = game_file.path

        try:
            # Detecta encoding
            encoding_detector = EncodingDetector(str(file_path))
            encoding_result = encoding_detector.detect()

            # Detecta formato
            format_detector = FileFormatDetector(str(file_path))
            format_structure = format_detector.detect()

            # Extrai baseado no formato
            if format_structure.format == FileFormat.JSON:
                self._extract_from_json(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.XML:
                self._extract_from_xml(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.YAML:
                self._extract_from_yaml(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.INI:
                self._extract_from_ini(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.TOML:
                self._extract_from_toml(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.KEY_VALUE:
                self._extract_from_key_value(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.DELIMITED:
                self._extract_from_delimited(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.SCRIPT:
                self._extract_from_script(file_path, encoding_result, format_structure)

            elif format_structure.format == FileFormat.PLAIN_TEXT:
                self._extract_from_plain_text(file_path, encoding_result, format_structure)

            else:
                print(f"  ⚠️  {file_path.name}: Unknown format, skipping")

        except Exception as e:
            print(f"  ❌ {file_path.name}: Error during extraction: {e}")

    def _extract_from_json(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo JSON."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                data = json.load(f)

            texts = self._extract_json_strings(data, path="")

            for context, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=context,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="json"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (JSON)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: JSON parse error: {e}")

    def _extract_json_strings(self, data: Any, path: str, line_num: int = 1) -> List[Tuple[str, str, int]]:
        """Extrai recursivamente strings de estrutura JSON."""
        results = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, str) and len(value.strip()) >= self.MIN_TEXT_LENGTH:
                    results.append((current_path, value, line_num))
                    line_num += 1

                elif isinstance(value, (dict, list)):
                    nested_results = self._extract_json_strings(value, current_path, line_num)
                    results.extend(nested_results)
                    line_num += len(nested_results)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"

                if isinstance(item, str) and len(item.strip()) >= self.MIN_TEXT_LENGTH:
                    results.append((current_path, item, line_num))
                    line_num += 1

                elif isinstance(item, (dict, list)):
                    nested_results = self._extract_json_strings(item, current_path, line_num)
                    results.extend(nested_results)
                    line_num += len(nested_results)

        return results

    def _extract_from_xml(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo XML."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            texts = self._extract_xml_text_nodes(root, path=root.tag)

            for xpath, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=xpath,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="xml"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (XML)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: XML parse error: {e}")

    def _extract_xml_text_nodes(self, element: ET.Element, path: str, line_num: int = 1) -> List[Tuple[str, str, int]]:
        """Extrai recursivamente textos de elementos XML."""
        results = []

        # Texto do elemento atual
        if element.text and element.text.strip() and len(element.text.strip()) >= self.MIN_TEXT_LENGTH:
            results.append((path, element.text.strip(), line_num))
            line_num += 1

        # Atributos que podem conter texto
        for attr_name, attr_value in element.attrib.items():
            if isinstance(attr_value, str) and len(attr_value.strip()) >= self.MIN_TEXT_LENGTH:
                # Evita atributos técnicos
                if attr_name.lower() not in {'id', 'class', 'type', 'name', 'encoding', 'version'}:
                    attr_path = f"{path}[@{attr_name}]"
                    results.append((attr_path, attr_value.strip(), line_num))
                    line_num += 1

        # Elementos filhos
        for child in element:
            child_path = f"{path}/{child.tag}"
            child_results = self._extract_xml_text_nodes(child, child_path, line_num)
            results.extend(child_results)
            line_num += len(child_results)

        return results

    def _extract_from_yaml(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo YAML."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                lines = f.readlines()

            # Extração simples via regex (sem biblioteca yaml)
            pattern = re.compile(r'^[\s]*([^:]+):\s*(.+)$')

            texts = []
            for i, line in enumerate(lines, 1):
                match = pattern.match(line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()

                    # Remove aspas se houver
                    value = value.strip('"\'')

                    if len(value) >= self.MIN_TEXT_LENGTH and not value.startswith('{'):
                        texts.append((key, value, i))

            for key, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=key,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="yaml"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (YAML)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: YAML parse error: {e}")

    def _extract_from_ini(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo INI."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                lines = f.readlines()

            current_section = "root"
            texts = []

            for i, line in enumerate(lines, 1):
                line = line.strip()

                # Ignora comentários e linhas vazias
                if not line or line.startswith(('#', ';')):
                    continue

                # Seção
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    continue

                # Key=Value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if len(value) >= self.MIN_TEXT_LENGTH:
                        context = f"{current_section}.{key}"
                        texts.append((context, value, i))

            for context, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=context,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="ini"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (INI)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: INI parse error: {e}")

    def _extract_from_toml(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo TOML (similar a INI)."""
        # TOML é similar a INI, reutiliza lógica
        self._extract_from_ini(file_path, encoding, structure)

    def _extract_from_key_value(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo key-value simples."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                lines = f.readlines()

            separator = structure.delimiter or '='
            texts = []

            for i, line in enumerate(lines, 1):
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                if separator in line:
                    parts = line.split(separator, 1)
                    if len(parts) == 2:
                        key, value = parts
                        value = value.strip()

                        if len(value) >= self.MIN_TEXT_LENGTH:
                            texts.append((key.strip(), value, i))

            for key, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=key,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="key_value"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (Key-Value)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: Key-Value parse error: {e}")

    def _extract_from_delimited(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai textos de arquivo delimitado (CSV, TSV)."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                lines = f.readlines()

            delimiter = structure.delimiter or ','
            start_line = 1 if structure.has_header else 0

            texts = []

            for i, line in enumerate(lines[start_line:], start_line + 1):
                columns = line.strip().split(delimiter)

                for col_idx, value in enumerate(columns):
                    value = value.strip().strip('"\'')

                    if len(value) >= self.MIN_TEXT_LENGTH:
                        context = f"row{i}.col{col_idx}"
                        texts.append((context, value, i))

            for context, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=context,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="delimited"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (Delimited)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: Delimited parse error: {e}")

    def _extract_from_script(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai strings literais de scripts (Lua, JS, Python)."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                content = f.read()

            # Padrões de strings em scripts
            patterns = [
                re.compile(r'"([^"\\]*(\\.[^"\\]*)*)"'),  # "double quotes"
                re.compile(r"'([^'\\]*(\\.[^'\\]*)*)'"),  # 'single quotes'
            ]

            texts = []
            seen_texts = set()  # Evita duplicatas

            for pattern in patterns:
                for match in pattern.finditer(content):
                    text = match.group(1)

                    # Remove escapes
                    text = text.replace('\\n', '\n').replace('\\t', '\t')
                    text = text.replace('\\"', '"').replace("\\'", "'")

                    if len(text.strip()) >= self.MIN_TEXT_LENGTH and text not in seen_texts:
                        # Calcula número da linha aproximado
                        line_num = content[:match.start()].count('\n') + 1

                        context = f"string_literal_line{line_num}"
                        texts.append((context, text, line_num))
                        seen_texts.add(text)

            for context, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=context,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="script"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} strings (Script)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: Script parse error: {e}")

    def _extract_from_plain_text(self, file_path: Path, encoding: EncodingResult, structure: FormatStructure):
        """Extrai linhas de arquivo de texto puro."""
        try:
            with open(file_path, 'r', encoding=encoding.encoding, errors='replace') as f:
                lines = f.readlines()

            texts = []

            for i, line in enumerate(lines, 1):
                text = line.strip()

                if len(text) >= self.MIN_TEXT_LENGTH:
                    context = f"line{i}"
                    texts.append((context, text, i))

            for context, text, line_num in texts:
                self._add_text(
                    file_path=str(file_path.relative_to(self.game_path)),
                    line_number=line_num,
                    context=context,
                    original_text=text,
                    encoding=encoding.encoding,
                    format="plain_text"
                )

            print(f"  ✓ {file_path.name}: {len(texts)} lines (Plain Text)")

        except Exception as e:
            print(f"  ✗ {file_path.name}: Plain text read error: {e}")

    def _add_text(self, file_path: str, line_number: Optional[int], context: str,
                  original_text: str, encoding: str, format: str):
        """Adiciona texto extraído à lista."""
        extracted = ExtractedText(
            id=self.next_id,
            file_path=file_path,
            line_number=line_number,
            context=context,
            original_text=original_text,
            encoding=encoding,
            format=format,
            extractable=True,
            metadata={}
        )

        self.extracted_texts.append(extracted)
        self.next_id += 1

    def _filter_non_translatable(self):
        """Marca textos não traduzíveis (URLs, caminhos, etc)."""
        for text_entry in self.extracted_texts:
            # Verifica padrões não traduzíveis
            for pattern in self.NON_TRANSLATABLE_PATTERNS:
                if pattern.match(text_entry.original_text):
                    text_entry.extractable = False
                    text_entry.metadata['skip_reason'] = 'non_translatable_pattern'
                    break

            # Textos muito curtos
            if len(text_entry.original_text.strip()) < self.MIN_TEXT_LENGTH:
                text_entry.extractable = False
                text_entry.metadata['skip_reason'] = 'too_short'

    def export_to_json(self, output_path: str):
        """Exporta textos extraídos para JSON."""
        export_data = {
            'extraction_info': {
                'game_path': str(self.game_path),
                'timestamp': datetime.now().isoformat(),
                'total_texts': len(self.extracted_texts),
                'translatable_texts': sum(1 for t in self.extracted_texts if t.extractable),
            },
            'texts': [
                text.to_dict() for text in self.extracted_texts
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Extraction data exported to: {output_path}")

    def get_translatable_texts(self) -> List[ExtractedText]:
        """Retorna apenas textos traduzíveis."""
        return [t for t in self.extracted_texts if t.extractable]


def extract_game_texts(game_path: str, min_priority: int = 30, export_json: bool = True) -> PCTextExtractor:
    """
    Função de conveniência para extração direta.

    Args:
        game_path: Caminho do jogo
        min_priority: Prioridade mínima de arquivo
        export_json: Se True, exporta JSON

    Returns:
        PCTextExtractor com textos extraídos
    """
    extractor = PCTextExtractor(game_path)
    extractor.extract_all(min_priority=min_priority)

    if export_json:
        output_path = Path(game_path) / 'extracted_texts_pc.json'
        extractor.export_to_json(str(output_path))

    return extractor


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pc_text_extractor.py <game_directory>")
        print("\nExample:")
        print('  python pc_text_extractor.py "C:\\Games\\MyGame"')
        sys.exit(1)

    game_dir = sys.argv[1]
    extractor = extract_game_texts(game_dir, min_priority=30, export_json=True)

    # Exibe resumo
    translatable = extractor.get_translatable_texts()

    print(f"\n📊 EXTRACTION SUMMARY")
    print(f"{'='*70}")
    print(f"Total texts extracted: {len(extractor.extracted_texts)}")
    print(f"Translatable texts: {len(translatable)}")
    print(f"Non-translatable: {len(extractor.extracted_texts) - len(translatable)}")

    # Agrupa por formato
    by_format = {}
    for text in translatable:
        by_format[text.format] = by_format.get(text.format, 0) + 1

    print(f"\nTEXTS BY FORMAT:")
    for format_type, count in sorted(by_format.items(), key=lambda x: x[1], reverse=True):
        print(f"  {format_type:15s}: {count:4d}")

    # Top 10 textos
    print(f"\nSAMPLE TEXTS (first 10):")
    for text in translatable[:10]:
        preview = text.original_text[:50] + "..." if len(text.original_text) > 50 else text.original_text
        print(f"  [{text.id:3d}] {text.file_path}:{text.line_number or '?'}")
        print(f"        {text.context} = \"{preview}\"")

    print(f"\n{'='*70}\n")
