# -*- coding: utf-8 -*-
"""
================================================================================
FILE FORMAT DETECTOR - Detecção Automática de Estrutura de Arquivos
================================================================================
Identifica automaticamente o formato interno de arquivos de texto de jogos:
- JSON, XML, YAML, TOML, INI
- Formatos proprietários estruturados (key=value, CSV-like)
- Arquivos com delimitadores especiais
- Preservação de estrutura para reinserção segura

NÃO assume formato específico - análise heurística do conteúdo
================================================================================
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from enum import Enum


class FileFormat(Enum):
    """Formatos de arquivo detectados."""
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    INI = "ini"
    TOML = "toml"
    CSV = "csv"
    KEY_VALUE = "key_value"          # key=value ou key: value
    PLAIN_TEXT = "plain_text"        # Texto puro sem estrutura
    DELIMITED = "delimited"          # Delimitadores especiais (|, tab, etc)
    SCRIPT = "script"                # Lua, JS, etc com strings
    BINARY_TEXT = "binary_text"      # Binário com strings embutidas
    UNKNOWN = "unknown"


class FormatStructure:
    """Representa a estrutura detectada de um arquivo."""

    def __init__(self, format_type: FileFormat):
        self.format = format_type
        self.encoding = 'utf-8'
        self.delimiter = None
        self.has_header = False
        self.line_pattern = None
        self.text_locations: List[Dict] = []  # Onde está o texto traduzível
        self.metadata = {}

    def __repr__(self):
        return f"<FormatStructure {self.format.value} encoding={self.encoding}>"


class FileFormatDetector:
    """
    Detector universal de formatos de arquivo.
    Identifica estrutura sem conhecimento prévio.
    """

    def __init__(self, file_path: str):
        """
        Args:
            file_path: Caminho do arquivo para analisar
        """
        self.file_path = Path(file_path)
        self.structure: Optional[FormatStructure] = None
        self.content_sample = None

    def detect(self) -> FormatStructure:
        """
        Executa detecção completa do formato.

        Returns:
            FormatStructure com formato identificado
        """
        # Lê amostra do arquivo
        self.content_sample = self._read_sample()

        # Tenta detectar por conteúdo
        detected_format = self._detect_format()

        self.structure = FormatStructure(detected_format)

        # Detecções específicas por formato
        if detected_format == FileFormat.JSON:
            self._analyze_json()
        elif detected_format == FileFormat.XML:
            self._analyze_xml()
        elif detected_format == FileFormat.YAML:
            self._analyze_yaml()
        elif detected_format == FileFormat.INI:
            self._analyze_ini()
        elif detected_format == FileFormat.KEY_VALUE:
            self._analyze_key_value()
        elif detected_format == FileFormat.DELIMITED:
            self._analyze_delimited()
        elif detected_format == FileFormat.SCRIPT:
            self._analyze_script()
        elif detected_format == FileFormat.BINARY_TEXT:
            self._analyze_binary_text()

        return self.structure

    def _read_sample(self, sample_size: int = 8192) -> bytes:
        """Lê amostra do arquivo para análise."""
        try:
            with open(self.file_path, 'rb') as f:
                return f.read(sample_size)
        except Exception as e:
            print(f"⚠️  Error reading file: {e}")
            return b''

    def _detect_format(self) -> FileFormat:
        """
        Detecta formato baseado em heurísticas.

        Ordem de tentativa (do mais específico para o mais genérico):
        1. JSON (começa com { ou [)
        2. XML (começa com < ou <?xml)
        3. YAML (padrão key: value com indentação)
        4. INI (seções [section])
        5. TOML (seções [section] + key = value)
        6. CSV/Delimited (padrão de colunas)
        7. Key-Value (linhas key=value)
        8. Script (padrões de strings em código)
        9. Plain text
        """
        # Tenta decodificar como texto
        text_content = None
        for encoding in ['utf-8', 'utf-16-le', 'utf-16-be', 'windows-1252', 'latin-1']:
            try:
                text_content = self.content_sample.decode(encoding)
                self.structure.encoding if self.structure else None
                break
            except UnicodeDecodeError:
                continue

        if text_content is None:
            # É binário
            # Mas pode conter strings
            if self._has_embedded_strings(self.content_sample):
                return FileFormat.BINARY_TEXT
            return FileFormat.UNKNOWN

        # Remove linhas vazias e espaços para análise
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]

        if not lines:
            return FileFormat.PLAIN_TEXT

        # 1. JSON
        if self._is_json(text_content):
            return FileFormat.JSON

        # 2. XML
        if self._is_xml(text_content):
            return FileFormat.XML

        # 3. YAML
        if self._is_yaml(lines):
            return FileFormat.YAML

        # 4. INI
        if self._is_ini(lines):
            return FileFormat.INI

        # 5. TOML
        if self._is_toml(lines):
            return FileFormat.TOML

        # 6. CSV/Delimited
        if self._is_delimited(lines):
            return FileFormat.DELIMITED

        # 7. Key-Value
        if self._is_key_value(lines):
            return FileFormat.KEY_VALUE

        # 8. Script (Lua, JS, etc)
        if self._is_script(text_content):
            return FileFormat.SCRIPT

        # 9. Plain text (fallback)
        return FileFormat.PLAIN_TEXT

    def _is_json(self, content: str) -> bool:
        """Verifica se é JSON válido."""
        content = content.strip()
        if not (content.startswith('{') or content.startswith('[')):
            return False

        try:
            json.loads(content)
            return True
        except json.JSONDecodeError:
            return False

    def _is_xml(self, content: str) -> bool:
        """Verifica se é XML."""
        content = content.strip()
        return content.startswith('<') and ('>' in content)

    def _is_yaml(self, lines: List[str]) -> bool:
        """Verifica se é YAML (padrão key: value com indentação)."""
        yaml_pattern = re.compile(r'^[\w\s]+:\s*.+$')

        yaml_lines = sum(1 for line in lines if yaml_pattern.match(line))

        return yaml_lines / len(lines) > 0.4  # Pelo menos 40% das linhas

    def _is_ini(self, lines: List[str]) -> bool:
        """Verifica se é INI (seções [section])."""
        has_sections = any(line.startswith('[') and line.endswith(']') for line in lines)

        key_value_pattern = re.compile(r'^[\w\s]+\s*=\s*.+$')
        has_key_values = any(key_value_pattern.match(line) for line in lines)

        return has_sections and has_key_values

    def _is_toml(self, lines: List[str]) -> bool:
        """Verifica se é TOML."""
        # Similar a INI mas com sintaxe mais restrita
        section_pattern = re.compile(r'^\[[\w\.]+\]$')
        has_sections = any(section_pattern.match(line) for line in lines)

        key_value_pattern = re.compile(r'^[\w_]+\s*=\s*.+$')
        has_key_values = any(key_value_pattern.match(line) for line in lines)

        return has_sections and has_key_values

    def _is_delimited(self, lines: List[str]) -> bool:
        """Verifica se é arquivo delimitado (CSV, TSV, pipe-separated)."""
        if len(lines) < 2:
            return False

        # Testa delimitadores comuns
        delimiters = [',', '\t', '|', ';']

        for delim in delimiters:
            # Conta colunas em cada linha
            column_counts = [len(line.split(delim)) for line in lines[:10]]

            # Se a maioria das linhas tem mesmo número de colunas > 1
            if column_counts and max(set(column_counts), key=column_counts.count) > 1:
                most_common_count = max(set(column_counts), key=column_counts.count)
                if column_counts.count(most_common_count) / len(column_counts) > 0.7:
                    return True

        return False

    def _is_key_value(self, lines: List[str]) -> bool:
        """Verifica se é formato key=value ou key:value simples."""
        patterns = [
            re.compile(r'^[\w\s]+\s*=\s*.+$'),  # key = value
            re.compile(r'^[\w\s]+\s*:\s*.+$'),  # key: value
        ]

        for pattern in patterns:
            matches = sum(1 for line in lines if pattern.match(line))
            if matches / len(lines) > 0.5:  # Mais de 50%
                return True

        return False

    def _is_script(self, content: str) -> bool:
        """Verifica se é arquivo de script com strings."""
        # Padrões de strings em scripts
        string_patterns = [
            r'["\'].*?["\']',  # "text" ou 'text'
            r'function\s+\w+',  # function name()
            r'var\s+\w+',       # var name
            r'local\s+\w+',     # local name (Lua)
            r'def\s+\w+',       # def name (Python)
        ]

        script_indicators = sum(
            1 for pattern in string_patterns
            if re.search(pattern, content)
        )

        return script_indicators >= 2

    def _has_embedded_strings(self, data: bytes) -> bool:
        """Verifica se binário tem strings ASCII embutidas."""
        # Procura sequências de bytes ASCII imprimíveis
        ascii_sequences = re.findall(b'[\x20-\x7E]{4,}', data)

        return len(ascii_sequences) > 5  # Pelo menos 5 strings

    def _analyze_json(self):
        """Analisa estrutura JSON."""
        try:
            with open(self.file_path, 'r', encoding=self.structure.encoding) as f:
                data = json.load(f)

            # Encontra todas as chaves com valores de texto
            self.structure.text_locations = self._find_json_text_nodes(data)

        except Exception as e:
            print(f"⚠️  Error analyzing JSON: {e}")

    def _find_json_text_nodes(self, data: Any, path: str = "") -> List[Dict]:
        """Encontra recursivamente nós de texto em JSON."""
        locations = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, str) and len(value) > 0:
                    # É texto traduzível
                    locations.append({
                        'path': current_path,
                        'type': 'string',
                        'value': value
                    })
                elif isinstance(value, (dict, list)):
                    # Recursão
                    locations.extend(self._find_json_text_nodes(value, current_path))

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"

                if isinstance(item, str) and len(item) > 0:
                    locations.append({
                        'path': current_path,
                        'type': 'string',
                        'value': item
                    })
                elif isinstance(item, (dict, list)):
                    locations.extend(self._find_json_text_nodes(item, current_path))

        return locations

    def _analyze_xml(self):
        """Analisa estrutura XML."""
        # Detecta tags principais
        content = self.content_sample.decode(self.structure.encoding, errors='ignore')

        # Encontra tags
        tags = re.findall(r'<(\w+)>', content)
        unique_tags = list(set(tags))

        self.structure.metadata['tags'] = unique_tags[:20]  # Primeiras 20 tags únicas

    def _analyze_yaml(self):
        """Analisa estrutura YAML."""
        # Detecta chaves principais
        content = self.content_sample.decode(self.structure.encoding, errors='ignore')
        lines = content.split('\n')

        keys = []
        for line in lines:
            match = re.match(r'^([\w\s]+):\s*.+$', line.strip())
            if match:
                keys.append(match.group(1).strip())

        self.structure.metadata['sample_keys'] = list(set(keys))[:20]

    def _analyze_ini(self):
        """Analisa estrutura INI."""
        content = self.content_sample.decode(self.structure.encoding, errors='ignore')
        lines = content.split('\n')

        sections = [line.strip('[').strip(']') for line in lines if line.strip().startswith('[')]
        self.structure.metadata['sections'] = sections

    def _analyze_key_value(self):
        """Analisa estrutura key-value."""
        content = self.content_sample.decode(self.structure.encoding, errors='ignore')

        # Detecta separador (= ou :)
        if '=' in content:
            self.structure.delimiter = '='
        elif ':' in content:
            self.structure.delimiter = ':'

    def _analyze_delimited(self):
        """Analisa arquivo delimitado."""
        content = self.content_sample.decode(self.structure.encoding, errors='ignore')
        lines = content.split('\n')[:10]

        # Detecta delimitador
        for delim in [',', '\t', '|', ';']:
            if all(delim in line for line in lines if line.strip()):
                self.structure.delimiter = delim
                break

        # Primeira linha pode ser header
        if self.structure.delimiter:
            first_line = lines[0].split(self.structure.delimiter)
            # Se primeira linha tem palavras sem números, provavelmente é header
            if all(not any(c.isdigit() for c in col) for col in first_line):
                self.structure.has_header = True

    def _analyze_script(self):
        """Analisa arquivo de script."""
        # Detecta linguagem por extensão ou padrões
        ext = self.file_path.suffix.lower()

        language_map = {
            '.lua': 'lua',
            '.js': 'javascript',
            '.py': 'python',
            '.rb': 'ruby',
            '.cs': 'csharp',
        }

        self.structure.metadata['language'] = language_map.get(ext, 'unknown')

    def _analyze_binary_text(self):
        """Analisa binário com strings embutidas."""
        # Extrai strings ASCII
        strings = re.findall(b'[\x20-\x7E]{4,}', self.content_sample)

        self.structure.text_locations = [
            {'offset': self.content_sample.find(s), 'text': s.decode('ascii', errors='ignore')}
            for s in strings[:50]  # Primeiras 50 strings
        ]


def detect_file_format(file_path: str) -> FormatStructure:
    """
    Função de conveniência para detecção direta.

    Args:
        file_path: Caminho do arquivo

    Returns:
        FormatStructure com formato detectado
    """
    detector = FileFormatDetector(file_path)
    return detector.detect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python file_format_detector.py <file_path>")
        sys.exit(1)

    file = sys.argv[1]
    structure = detect_file_format(file)

    print(f"\n📄 FILE FORMAT DETECTION")
    print(f"{'='*70}")
    print(f"File: {file}")
    print(f"Format: {structure.format.value}")
    print(f"Encoding: {structure.encoding}")
    if structure.delimiter:
        print(f"Delimiter: {repr(structure.delimiter)}")
    if structure.has_header:
        print(f"Has header: Yes")
    if structure.metadata:
        print(f"Metadata: {structure.metadata}")
    if structure.text_locations:
        print(f"\nText locations found: {len(structure.text_locations)}")
        for loc in structure.text_locations[:5]:
            print(f"  {loc}")
    print(f"{'='*70}\n")
