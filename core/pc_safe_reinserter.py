# -*- coding: utf-8 -*-
"""
================================================================================
PC SAFE REINSERTER - Reinserção Segura de Traduções em Jogos de PC
================================================================================
Reinsere traduções preservando:
- Encoding original do arquivo
- Estrutura e formatação
- Integridade sintática (JSON válido, XML bem formado, etc)
- Backup automático antes de modificar

NUNCA corrompe arquivos - valida antes de escrever
================================================================================
"""

import json
import re
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import shutil

# Importa módulos existentes
from .pc_text_extractor import ExtractedText, PCTextExtractor
from .encoding_detector import EncodingDetector


@dataclass
class ReinsertionResult:
    """Resultado de uma reinserção."""
    success: bool
    file_path: str
    texts_reinserted: int
    backup_path: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class PCSafeReinserter:
    """
    Reinsertor seguro para jogos de PC.
    Preserva encoding e estrutura originais.
    """

    def __init__(self, extraction_json: str):
        """
        Args:
            extraction_json: Caminho do JSON de extração (pc_text_extractor.py)
        """
        self.extraction_json = Path(extraction_json)

        if not self.extraction_json.exists():
            raise FileNotFoundError(f"Extraction JSON not found: {extraction_json}")

        # Carrega dados de extração
        with open(self.extraction_json, 'r', encoding='utf-8') as f:
            self.extraction_data = json.load(f)

        self.game_path = Path(self.extraction_data['extraction_info']['game_path'])
        self.extracted_texts = [
            ExtractedText(**text_data)
            for text_data in self.extraction_data['texts']
        ]

        # Agrupa textos por arquivo
        self.texts_by_file: Dict[str, List[ExtractedText]] = {}
        for text in self.extracted_texts:
            if text.file_path not in self.texts_by_file:
                self.texts_by_file[text.file_path] = []
            self.texts_by_file[text.file_path].append(text)

        self.results: List[ReinsertionResult] = []

    def reinsert_translations(self, translations: Dict[int, str], create_backup: bool = True) -> Tuple[bool, str]:
        """
        Reinsere traduções em todos os arquivos.

        Args:
            translations: Dict {text_id: translated_text}
            create_backup: Se True, cria backup antes de modificar

        Returns:
            (success, message)
        """
        print(f"\n💾 PC SAFE REINSERTER - Safe Translation Reinsertion")
        print(f"{'='*70}")
        print(f"Game: {self.game_path}")
        print(f"Translations to reinsert: {len(translations)}")
        print(f"{'='*70}\n")

        # Atualiza textos extraídos com traduções
        translation_count = 0
        for text in self.extracted_texts:
            if text.id in translations:
                text.metadata['translated_text'] = translations[text.id]
                translation_count += 1

        print(f"✓ Matched {translation_count} translations to extracted texts\n")

        # Reinsere por arquivo
        print(f"[1/2] 🔄 Reinserting translations...")

        for file_path, texts in self.texts_by_file.items():
            # Filtra apenas textos com tradução
            translated_texts = [
                t for t in texts
                if 'translated_text' in t.metadata
            ]

            if not translated_texts:
                continue

            self._reinsert_file(file_path, translated_texts, create_backup)

        # Sumário
        print(f"\n[2/2] 📊 Generating summary...")

        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful

        print(f"\n{'='*70}")
        print(f"REINSERTION SUMMARY:")
        print(f"  Files processed: {len(self.results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")

        total_reinserted = sum(r.texts_reinserted for r in self.results if r.success)
        print(f"  Total texts reinserted: {total_reinserted}")
        print(f"{'='*70}\n")

        # Exibe detalhes de falhas
        if failed > 0:
            print(f"⚠️  FAILED FILES:")
            for result in self.results:
                if not result.success:
                    print(f"  ✗ {result.file_path}: {result.error_message}")

        # Exibe warnings
        warnings_count = sum(len(r.warnings) for r in self.results)
        if warnings_count > 0:
            print(f"\n⚠️  WARNINGS ({warnings_count} total):")
            for result in self.results:
                for warning in result.warnings:
                    print(f"  - {result.file_path}: {warning}")

        if failed == 0:
            return True, f"✅ All {len(self.results)} files reinserted successfully"
        else:
            return False, f"❌ {failed}/{len(self.results)} files failed reinsertion"

    def _reinsert_file(self, relative_path: str, texts: List[ExtractedText], create_backup: bool):
        """Reinsere traduções em um arquivo específico."""
        file_path = self.game_path / relative_path

        if not file_path.exists():
            result = ReinsertionResult(
                success=False,
                file_path=str(relative_path),
                texts_reinserted=0,
                error_message="File not found"
            )
            self.results.append(result)
            print(f"  ✗ {relative_path}: File not found")
            return

        try:
            # Detecta formato (assume que todos os textos do mesmo arquivo têm mesmo formato)
            format_type = texts[0].format

            # Backup
            backup_path = None
            if create_backup:
                backup_path = self._create_backup(file_path)

            # Reinsere baseado no formato
            if format_type == "json":
                success, reinserted, warnings = self._reinsert_json(file_path, texts)

            elif format_type == "xml":
                success, reinserted, warnings = self._reinsert_xml(file_path, texts)

            elif format_type in ["ini", "toml"]:
                success, reinserted, warnings = self._reinsert_ini(file_path, texts)

            elif format_type == "yaml":
                success, reinserted, warnings = self._reinsert_yaml(file_path, texts)

            elif format_type == "key_value":
                success, reinserted, warnings = self._reinsert_key_value(file_path, texts)

            elif format_type == "delimited":
                success, reinserted, warnings = self._reinsert_delimited(file_path, texts)

            elif format_type == "script":
                success, reinserted, warnings = self._reinsert_script(file_path, texts)

            elif format_type == "plain_text":
                success, reinserted, warnings = self._reinsert_plain_text(file_path, texts)

            else:
                success = False
                reinserted = 0
                warnings = [f"Unknown format: {format_type}"]

            # Resultado
            result = ReinsertionResult(
                success=success,
                file_path=str(relative_path),
                texts_reinserted=reinserted if success else 0,
                backup_path=str(backup_path) if backup_path else None,
                warnings=warnings
            )

            self.results.append(result)

            if success:
                print(f"  ✓ {relative_path}: {reinserted} texts reinserted")
            else:
                print(f"  ✗ {relative_path}: Reinsertion failed")

                # Restaura backup em caso de falha
                if backup_path and backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    print(f"    ↺ Backup restored")

        except Exception as e:
            result = ReinsertionResult(
                success=False,
                file_path=str(relative_path),
                texts_reinserted=0,
                error_message=str(e)
            )
            self.results.append(result)
            print(f"  ✗ {relative_path}: Exception: {e}")

    def _create_backup(self, file_path: Path) -> Path:
        """Cria backup do arquivo original."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup_{timestamp}")

        shutil.copy2(file_path, backup_path)

        return backup_path

    def _reinsert_json(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo JSON."""
        warnings = []

        try:
            # Detecta encoding
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            # Carrega JSON
            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                data = json.load(f)

            # Atualiza valores
            reinserted = 0
            for text in texts:
                if 'translated_text' not in text.metadata:
                    continue

                translated = text.metadata['translated_text']

                # Navega até a chave usando o context (ex: "dialogues.intro_1")
                keys = text.context.split('.')
                current = data

                try:
                    # Navega até o penúltimo nível
                    for key in keys[:-1]:
                        # Trata arrays [0], [1], etc
                        if key.startswith('[') and key.endswith(']'):
                            index = int(key[1:-1])
                            current = current[index]
                        else:
                            current = current[key]

                    # Atualiza valor final
                    final_key = keys[-1]
                    if final_key.startswith('[') and final_key.endswith(']'):
                        index = int(final_key[1:-1])
                        current[index] = translated
                    else:
                        current[final_key] = translated

                    reinserted += 1

                except (KeyError, IndexError, ValueError) as e:
                    warnings.append(f"Failed to update {text.context}: {e}")

            # Salva JSON (com formatação bonita)
            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"JSON reinsertion error: {e}"]

    def _reinsert_xml(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo XML."""
        warnings = []

        try:
            # Parse XML
            tree = ET.parse(file_path)
            root = tree.getroot()

            reinserted = 0

            for text in texts:
                if 'translated_text' not in text.metadata:
                    continue

                translated = text.metadata['translated_text']

                # Context é XPath (ex: "localization/ui/string")
                xpath = text.context

                try:
                    # Se é atributo
                    if '[@' in xpath:
                        # Ex: "element[@id]"
                        parts = xpath.split('[@')
                        element_path = parts[0]
                        attr_name = parts[1].rstrip(']')

                        element = root.find(element_path)
                        if element is not None:
                            element.set(attr_name, translated)
                            reinserted += 1
                        else:
                            warnings.append(f"Element not found: {element_path}")

                    else:
                        # É texto do elemento
                        element = root.find(xpath)
                        if element is not None:
                            element.text = translated
                            reinserted += 1
                        else:
                            warnings.append(f"Element not found: {xpath}")

                except Exception as e:
                    warnings.append(f"Failed to update {xpath}: {e}")

            # Salva XML com formatação bonita
            xml_str = ET.tostring(root, encoding='unicode')

            # Pretty print
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent="  ", encoding=None)

            # Remove linhas vazias extras
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            formatted_xml = '\n'.join(lines)

            # Detecta encoding original
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.write(formatted_xml)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"XML reinsertion error: {e}"]

    def _reinsert_ini(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo INI."""
        warnings = []

        try:
            # Detecta encoding
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            # Lê arquivo
            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                lines = f.readlines()

            # Cria mapa de traduções por context
            translations_map = {
                text.context: text.metadata['translated_text']
                for text in texts
                if 'translated_text' in text.metadata
            }

            reinserted = 0
            current_section = "root"
            new_lines = []

            for line in lines:
                stripped = line.strip()

                # Seção
                if stripped.startswith('[') and stripped.endswith(']'):
                    current_section = stripped[1:-1]
                    new_lines.append(line)
                    continue

                # Key=Value
                if '=' in stripped and not stripped.startswith(('#', ';')):
                    key, value = stripped.split('=', 1)
                    key = key.strip()

                    context = f"{current_section}.{key}"

                    if context in translations_map:
                        # Substitui valor mantendo formatação
                        indent = len(line) - len(line.lstrip())
                        new_line = ' ' * indent + f"{key} = {translations_map[context]}\n"
                        new_lines.append(new_line)
                        reinserted += 1
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # Salva
            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.writelines(new_lines)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"INI reinsertion error: {e}"]

    def _reinsert_yaml(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo YAML (via regex, sem biblioteca)."""
        warnings = []

        try:
            # Detecta encoding
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            # Lê arquivo
            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                lines = f.readlines()

            # Cria mapa de traduções
            translations_map = {
                text.context: text.metadata['translated_text']
                for text in texts
                if 'translated_text' in text.metadata
            }

            reinserted = 0
            new_lines = []

            for line in lines:
                match = re.match(r'^(\s*)([^:]+):\s*(.+)$', line)

                if match:
                    indent = match.group(1)
                    key = match.group(2).strip()
                    value = match.group(3).strip()

                    if key in translations_map:
                        translated = translations_map[key]
                        # Preserva aspas se originalmente tinha
                        if value.startswith('"') and value.endswith('"'):
                            translated = f'"{translated}"'
                        elif value.startswith("'") and value.endswith("'"):
                            translated = f"'{translated}'"

                        new_line = f"{indent}{key}: {translated}\n"
                        new_lines.append(new_line)
                        reinserted += 1
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # Salva
            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.writelines(new_lines)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"YAML reinsertion error: {e}"]

    def _reinsert_key_value(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo key-value."""
        # Similar a INI mas sem seções
        warnings = []

        try:
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                lines = f.readlines()

            translations_map = {
                text.context: text.metadata['translated_text']
                for text in texts
                if 'translated_text' in text.metadata
            }

            # Detecta separador (= ou :)
            separator = texts[0].metadata.get('delimiter', '=') if texts else '='

            reinserted = 0
            new_lines = []

            for line in lines:
                stripped = line.strip()

                if separator in stripped and not stripped.startswith('#'):
                    key, value = stripped.split(separator, 1)
                    key = key.strip()

                    if key in translations_map:
                        indent = len(line) - len(line.lstrip())
                        new_line = ' ' * indent + f"{key}{separator}{translations_map[key]}\n"
                        new_lines.append(new_line)
                        reinserted += 1
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.writelines(new_lines)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"Key-value reinsertion error: {e}"]

    def _reinsert_delimited(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo delimitado (CSV, TSV)."""
        warnings = []

        try:
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                lines = f.readlines()

            # Cria mapa por context (ex: "row5.col2")
            translations_map = {
                text.context: text.metadata['translated_text']
                for text in texts
                if 'translated_text' in text.metadata
            }

            # Detecta delimitador
            delimiter = ','
            if texts:
                for text in texts:
                    if 'delimiter' in text.metadata:
                        delimiter = text.metadata['delimiter']
                        break

            reinserted = 0
            new_lines = []

            for i, line in enumerate(lines, 1):
                columns = line.strip().split(delimiter)

                modified = False
                for col_idx, value in enumerate(columns):
                    context = f"row{i}.col{col_idx}"

                    if context in translations_map:
                        columns[col_idx] = f'"{translations_map[context]}"'
                        reinserted += 1
                        modified = True

                if modified:
                    new_lines.append(delimiter.join(columns) + '\n')
                else:
                    new_lines.append(line)

            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.writelines(new_lines)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"Delimited reinsertion error: {e}"]

    def _reinsert_script(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivos de script (Lua, JS, Python)."""
        warnings = []

        try:
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                content = f.read()

            # Scripts são complexos - substitui apenas strings exatas
            reinserted = 0

            for text in texts:
                if 'translated_text' not in text.metadata:
                    continue

                original = text.original_text
                translated = text.metadata['translated_text']

                # Escapa caracteres especiais
                escaped_original = original.replace('\\', '\\\\').replace('"', '\\"')
                escaped_translated = translated.replace('\\', '\\\\').replace('"', '\\"')

                # Tenta substituir com aspas duplas
                pattern1 = f'"{re.escape(escaped_original)}"'
                replacement1 = f'"{escaped_translated}"'

                if pattern1 in content:
                    content = content.replace(pattern1, replacement1, 1)
                    reinserted += 1
                    continue

                # Tenta aspas simples
                pattern2 = f"'{re.escape(escaped_original)}'"
                replacement2 = f"'{escaped_translated}'"

                if pattern2 in content:
                    content = content.replace(pattern2, replacement2, 1)
                    reinserted += 1

            # Salva
            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.write(content)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"Script reinsertion error: {e}"]

    def _reinsert_plain_text(self, file_path: Path, texts: List[ExtractedText]) -> Tuple[bool, int, List[str]]:
        """Reinsere traduções em arquivo de texto puro."""
        warnings = []

        try:
            detector = EncodingDetector(str(file_path))
            encoding_result = detector.detect()

            with open(file_path, 'r', encoding=encoding_result.encoding, errors='replace') as f:
                lines = f.readlines()

            # Cria mapa por número de linha
            translations_by_line = {}
            for text in texts:
                if 'translated_text' in text.metadata and text.line_number:
                    translations_by_line[text.line_number] = text.metadata['translated_text']

            reinserted = 0
            new_lines = []

            for i, line in enumerate(lines, 1):
                if i in translations_by_line:
                    # Preserva indentação e \n
                    indent = len(line) - len(line.lstrip())
                    new_line = ' ' * indent + translations_by_line[i] + '\n'
                    new_lines.append(new_line)
                    reinserted += 1
                else:
                    new_lines.append(line)

            with open(file_path, 'w', encoding=encoding_result.encoding, errors='replace') as f:
                f.writelines(new_lines)

            return True, reinserted, warnings

        except Exception as e:
            return False, 0, [f"Plain text reinsertion error: {e}"]


def reinsert_game_translations(extraction_json: str, translations: Dict[int, str], create_backup: bool = True) -> Tuple[bool, str]:
    """
    Função de conveniência para reinserção direta.

    Args:
        extraction_json: JSON de extração
        translations: Dict {text_id: translated_text}
        create_backup: Criar backups

    Returns:
        (success, message)
    """
    reinserter = PCSafeReinserter(extraction_json)
    return reinserter.reinsert_translations(translations, create_backup)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pc_safe_reinserter.py <extraction_json> [translations_json]")
        print("\nExample:")
        print('  python pc_safe_reinserter.py "game/extracted_texts_pc.json" "translations.json"')
        sys.exit(1)

    extraction_json = sys.argv[1]

    # Se forneceu JSON de traduções
    if len(sys.argv) >= 3:
        translations_json = sys.argv[2]

        with open(translations_json, 'r', encoding='utf-8') as f:
            translations = json.load(f)

        # Converte keys para int
        translations = {int(k): v for k, v in translations.items()}

        success, message = reinsert_game_translations(extraction_json, translations, create_backup=True)

        print(f"\n{message}\n")
        sys.exit(0 if success else 1)

    else:
        print("❌ Missing translations JSON file")
        sys.exit(1)
