# -*- coding: utf-8 -*-
"""
================================================================================
STRING CLASSIFIER - Classificação de Strings (Runtime vs Estáticas)
================================================================================
Identifica o tipo de cada string encontrada:

STATIC: Strings hardcoded no binário/código
- Mensagens de erro fixas
- Textos de menu
- Diálogos estáticos

RUNTIME: Strings geradas dinamicamente
- Templates com placeholders ({name}, %s, etc)
- Strings concatenadas em runtime
- Textos construídos por lógica

MIXED: Strings que misturam código e texto
- Scripts Lua/JS com strings embutidas
- Formatação condicional
- Lógica de exibição

CODE: Não é texto traduzível
- Identificadores de variáveis
- Nomes de funções
- Paths de arquivos

Usa: Análise de contexto, padrões sintáticos, heurísticas de código
================================================================================
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class StringType(Enum):
    """Tipo de string detectado."""
    STATIC = "static"              # Hardcoded, traduzível diretamente
    RUNTIME = "runtime"            # Gerada em runtime, requer atenção
    MIXED = "mixed"                # Mistura código + texto
    CODE = "code"                  # Não é texto, é identificador
    TEMPLATE = "template"          # Template com placeholders
    UNKNOWN = "unknown"


@dataclass
class StringClassification:
    """Resultado da classificação de uma string."""
    text: str
    type: StringType
    confidence: float  # 0.0 - 1.0
    translatable: bool
    placeholders: List[str] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.placeholders is None:
            self.placeholders = []
        if self.metadata is None:
            self.metadata = {}


class StringClassifier:
    """
    Classificador universal de strings.
    Identifica tipo e translatabilidade.
    """

    # Padrões de placeholders comuns
    PLACEHOLDER_PATTERNS = [
        # C-style
        (re.compile(r'%[sdifxX]'), 'c_style'),
        (re.compile(r'%\d+\$[sdif]'), 'c_style_positional'),

        # Python-style
        (re.compile(r'\{[\w\d_]+\}'), 'python_format'),
        (re.compile(r'\{\d+\}'), 'python_positional'),

        # Unity/C#
        (re.compile(r'\{[\w\d_]+:\w+\}'), 'csharp_format'),

        # Lua
        (re.compile(r'\$\{[\w\d_]+\}'), 'lua_interpolation'),

        # JavaScript
        (re.compile(r'\$\{[^}]+\}'), 'js_template'),

        # Custom placeholders
        (re.compile(r'<[\w\d_]+>'), 'xml_like'),
        (re.compile(r'\[[\w\d_]+\]'), 'bracket_style'),
    ]

    # Padrões que indicam código (não traduzível)
    CODE_PATTERNS = [
        re.compile(r'^[a-z_][a-z0-9_]*$', re.I),  # variavel_nome
        re.compile(r'^[A-Z_][A-Z0-9_]+$'),         # CONSTANTE
        re.compile(r'^[a-z]+\.[a-z]+$'),           # arquivo.ext
        re.compile(r'^/[\w/]+'),                   # /path/absoluto
        re.compile(r'^[a-z]:\\', re.I),            # C:\windows
        re.compile(r'^\w+\(\)$'),                  # funcao()
        re.compile(r'^#[0-9a-fA-F]{6}$'),          # #FF0000 (cor)
    ]

    # Padrões de código misturado
    MIXED_CODE_PATTERNS = [
        re.compile(r'if\s*\('),                    # if (
        re.compile(r'for\s*\('),                   # for (
        re.compile(r'while\s*\('),                 # while (
        re.compile(r'function\s+\w+'),             # function nome
        re.compile(r'var\s+\w+'),                  # var nome
        re.compile(r'local\s+\w+'),                # local nome (Lua)
        re.compile(r'return\s+'),                  # return
        re.compile(r'=>'),                         # arrow function
    ]

    # Padrões de strings de runtime
    RUNTIME_PATTERNS = [
        re.compile(r'\+\s*["\']'),                 # concatenação: + "texto"
        re.compile(r'\.format\('),                 # .format(
        re.compile(r'\.concat\('),                 # .concat(
        re.compile(r'\.join\('),                   # .join(
        re.compile(r'\.replace\('),                # .replace(
    ]

    def __init__(self):
        """Inicializa classificador."""
        pass

    def classify(self, text: str, context: Optional[str] = None) -> StringClassification:
        """
        Classifica uma string.

        Args:
            text: Texto a classificar
            context: Contexto adicional (código ao redor, caminho do arquivo, etc)

        Returns:
            StringClassification
        """
        # 1. Verifica se é código puro
        if self._is_code(text):
            return StringClassification(
                text=text,
                type=StringType.CODE,
                confidence=0.9,
                translatable=False,
                metadata={'reason': 'code_pattern_match'}
            )

        # 2. Detecta placeholders
        placeholders, placeholder_types = self._detect_placeholders(text)

        # 3. Verifica código misturado
        if self._has_mixed_code(text):
            return StringClassification(
                text=text,
                type=StringType.MIXED,
                confidence=0.85,
                translatable=False,
                placeholders=placeholders,
                metadata={'reason': 'mixed_code', 'placeholder_types': placeholder_types}
            )

        # 4. Classifica por contexto (se fornecido)
        if context:
            context_result = self._classify_by_context(text, context)
            if context_result:
                context_result.placeholders = placeholders
                return context_result

        # 5. Classifica por conteúdo
        if placeholders:
            # Tem placeholders = template
            return StringClassification(
                text=text,
                type=StringType.TEMPLATE,
                confidence=0.9,
                translatable=True,
                placeholders=placeholders,
                metadata={'placeholder_types': placeholder_types}
            )

        # 6. Análise heurística
        heuristic_result = self._heuristic_classification(text)

        return heuristic_result

    def classify_batch(self, texts: List[str], contexts: Optional[List[str]] = None) -> List[StringClassification]:
        """
        Classifica múltiplas strings.

        Args:
            texts: Lista de textos
            contexts: Lista de contextos (opcional)

        Returns:
            Lista de StringClassification
        """
        if contexts is None:
            contexts = [None] * len(texts)

        return [self.classify(text, context) for text, context in zip(texts, contexts)]

    def _is_code(self, text: str) -> bool:
        """Verifica se é código/identificador."""
        text = text.strip()

        # Muito curto ou vazio
        if len(text) < 2:
            return True

        # Testa padrões de código
        for pattern in self.CODE_PATTERNS:
            if pattern.match(text):
                return True

        # Apenas números
        if text.isdigit():
            return True

        # Apenas símbolos
        if all(not c.isalnum() for c in text):
            return True

        return False

    def _detect_placeholders(self, text: str) -> tuple:
        """
        Detecta placeholders na string.

        Returns:
            (lista_placeholders, tipos_detectados)
        """
        placeholders = []
        types_found = set()

        for pattern, ptype in self.PLACEHOLDER_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                placeholders.extend(matches)
                types_found.add(ptype)

        return placeholders, list(types_found)

    def _has_mixed_code(self, text: str) -> bool:
        """Verifica se tem código misturado."""
        for pattern in self.MIXED_CODE_PATTERNS:
            if pattern.search(text):
                return True

        return False

    def _classify_by_context(self, text: str, context: str) -> Optional[StringClassification]:
        """Classifica baseado no contexto."""
        context_lower = context.lower()

        # Contexto de script (Lua, JS, etc)
        if any(ext in context_lower for ext in ['.lua', '.js', '.py', '.rb']):
            # Verifica se está em código
            if self._is_in_code_context(text, context):
                return StringClassification(
                    text=text,
                    type=StringType.MIXED,
                    confidence=0.8,
                    translatable=False,
                    metadata={'reason': 'script_code_context'}
                )

        # Contexto de arquivo de localização
        if any(name in context_lower for name in ['lang', 'locale', 'i18n', 'translation']):
            return StringClassification(
                text=text,
                type=StringType.STATIC,
                confidence=0.95,
                translatable=True,
                metadata={'reason': 'localization_file'}
            )

        # Contexto de configuração
        if any(name in context_lower for name in ['config', 'settings', '.ini']):
            # Verifica se é valor de config ou texto
            if '=' in text or ':' in text:
                return StringClassification(
                    text=text,
                    type=StringType.CODE,
                    confidence=0.7,
                    translatable=False,
                    metadata={'reason': 'config_value'}
                )

        return None

    def _is_in_code_context(self, text: str, context: str) -> bool:
        """Verifica se string está em contexto de código."""
        # Procura padrões de atribuição
        if re.search(r'\w+\s*=\s*["\']' + re.escape(text), context):
            return False  # É valor atribuído = traduzível

        # Procura padrões de função/método
        if re.search(r'\w+\(["\']' + re.escape(text), context):
            return False  # É argumento = traduzível

        # Se aparece sozinho em linha de código
        if re.search(r'(if|while|for|return)\s+["\']' + re.escape(text), context):
            return True  # É código

        return False

    def _heuristic_classification(self, text: str) -> StringClassification:
        """Classificação heurística final."""
        text_stripped = text.strip()

        # Strings muito curtas (1-2 chars) provavelmente são código
        if len(text_stripped) <= 2:
            return StringClassification(
                text=text,
                type=StringType.CODE,
                confidence=0.7,
                translatable=False,
                metadata={'reason': 'too_short'}
            )

        # Verifica proporção de caracteres alfanuméricos
        alphanum_ratio = sum(c.isalnum() for c in text_stripped) / len(text_stripped)

        # Muito baixo = não é texto natural
        if alphanum_ratio < 0.5:
            return StringClassification(
                text=text,
                type=StringType.CODE,
                confidence=0.6,
                translatable=False,
                metadata={'reason': 'low_alphanum_ratio', 'ratio': alphanum_ratio}
            )

        # Verifica espaços (texto natural tem espaços)
        has_spaces = ' ' in text_stripped

        # Verifica letras maiúsculas/minúsculas (texto natural mistura)
        has_mixed_case = any(c.islower() for c in text_stripped) and any(c.isupper() for c in text_stripped)

        # Heurística: texto natural
        if has_spaces and has_mixed_case:
            return StringClassification(
                text=text,
                type=StringType.STATIC,
                confidence=0.8,
                translatable=True,
                metadata={'reason': 'natural_language_pattern'}
            )

        # Heurística: tudo maiúsculo = pode ser constante
        if text_stripped.isupper() and len(text_stripped) > 5:
            return StringClassification(
                text=text,
                type=StringType.CODE,
                confidence=0.65,
                translatable=False,
                metadata={'reason': 'all_uppercase_constant'}
            )

        # Default: assume estático com confiança média
        return StringClassification(
            text=text,
            type=StringType.STATIC,
            confidence=0.5,
            translatable=True,
            metadata={'reason': 'default_heuristic'}
        )

    def get_translatable_only(self, classifications: List[StringClassification]) -> List[StringClassification]:
        """Retorna apenas strings traduzíveis."""
        return [c for c in classifications if c.translatable]

    def get_by_type(self, classifications: List[StringClassification], string_type: StringType) -> List[StringClassification]:
        """Retorna strings de um tipo específico."""
        return [c for c in classifications if c.type == string_type]


def classify_string(text: str, context: Optional[str] = None) -> StringClassification:
    """
    Função de conveniência para classificação rápida.

    Args:
        text: Texto a classificar
        context: Contexto opcional

    Returns:
        StringClassification
    """
    classifier = StringClassifier()
    return classifier.classify(text, context)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python string_classifier.py <text> [context]")
        print("\nExample:")
        print('  python string_classifier.py "Hello {name}!"')
        print('  python string_classifier.py "player_score" "game.lua"')
        sys.exit(1)

    text = sys.argv[1]
    context = sys.argv[2] if len(sys.argv) > 2 else None

    result = classify_string(text, context)

    print(f"\n📊 STRING CLASSIFICATION RESULT")
    print(f"{'='*70}")
    print(f"Text: {result.text}")
    print(f"Type: {result.type.value}")
    print(f"Confidence: {result.confidence * 100:.1f}%")
    print(f"Translatable: {'✅ Yes' if result.translatable else '❌ No'}")

    if result.placeholders:
        print(f"\nPlaceholders detected:")
        for ph in result.placeholders:
            print(f"  - {ph}")

    if result.metadata:
        print(f"\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    print(f"{'='*70}\n")

    # Exemplos de teste
    print("📋 TEST EXAMPLES:\n")

    test_cases = [
        ("Hello World!", None),
        ("player_name", None),
        ("Press {key} to continue", None),
        ("if (player.health > 0)", "script.lua"),
        ("#FF0000", None),
        ("C:\\Program Files\\Game", None),
        ("Welcome to %s, %s!", None),
        ("NEW_GAME", "menu.json"),
        ("new_game", "code.py"),
    ]

    for test_text, test_context in test_cases:
        result = classify_string(test_text, test_context)
        icon = "✅" if result.translatable else "❌"
        print(f"{icon} [{result.type.value:8s}] {test_text:30s} (conf: {result.confidence:.2f})")
