#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Text Validator - Detector de Texto Traduzível
==================================================

Diferencia texto humano real de lixo binário/técnico.
Previne alucinação de LLMs em ROM hacking.

Author: ROM Translation Framework
Version: 1.0.0
"""

import re
from typing import Tuple


class ROMTextValidator:
    """Valida se texto é traduzível ou binário/técnico."""

    # Códigos de controle comuns em ROMs
    CONTROL_CODES = [
        '<0A>', '<0D>', '<00>', '<FF>',
        '{VAR}', '{PLAYER}', '{ITEM}', '{NAME}',
        '[NAME]', '[PAUSE]', '[WAIT]', '[END]',
        '\\n', '\\r', '\\t', '\\x'
    ]

    # Ratio mínimo de caracteres imprimíveis
    MIN_PRINTABLE_RATIO = 0.85

    # Ratio mínimo de alfabéticos
    MIN_ALPHA_RATIO = 0.70

    # Comprimento mínimo para texto válido
    MIN_LENGTH = 3

    # Ratio máximo de símbolos repetidos
    MAX_REPEAT_RATIO = 0.70

    @staticmethod
    def is_control_code_heavy(text: str) -> bool:
        """
        Verifica se texto é majoritariamente códigos de controle.

        Args:
            text: Texto a validar

        Returns:
            True se > 50% são códigos de controle
        """
        control_chars = 0
        total_chars = len(text)

        if total_chars == 0:
            return True

        for code in ROMTextValidator.CONTROL_CODES:
            control_chars += text.count(code) * len(code)

        return (control_chars / total_chars) > 0.50

    @staticmethod
    def is_binary_garbage(text: str) -> bool:
        """
        Detecta sequências que parecem dados binários.

        Args:
            text: Texto a validar

        Returns:
            True se parece lixo binário
        """
        if not text or len(text) < ROMTextValidator.MIN_LENGTH:
            return True

        # Remove códigos de controle conhecidos para análise
        clean_text = text
        for code in ROMTextValidator.CONTROL_CODES:
            clean_text = clean_text.replace(code, '')

        if not clean_text:
            return True  # Apenas códigos de controle

        # COMMERCIAL GRADE: Strings > 3 chars MUST have at least 1 vowel
        if len(clean_text) > 3:
            vowels = 'aeiouAEIOU'
            has_vowel = any(c in vowels for c in clean_text)
            if not has_vowel:
                return True  # NO VOWELS = GARBAGE (e.g., "TSRRQPP", "XYZ", "JKL")

        # Conta caracteres imprimíveis
        printable = sum(1 for c in clean_text if c.isprintable() or c.isspace())
        printable_ratio = printable / len(clean_text)

        if printable_ratio < ROMTextValidator.MIN_PRINTABLE_RATIO:
            return True  # Muitos caracteres não-imprimíveis

        # Conta alfabéticos
        alpha = sum(1 for c in clean_text if c.isalpha())
        alpha_ratio = alpha / len(clean_text) if len(clean_text) > 0 else 0

        if alpha_ratio < ROMTextValidator.MIN_ALPHA_RATIO:
            return True  # Muito pouco texto alfabético

        # Detecta repetições excessivas (padding)
        if len(clean_text) > 0:
            most_common_char = max(set(clean_text), key=clean_text.count)
            repeat_ratio = clean_text.count(most_common_char) / len(clean_text)

            if repeat_ratio > ROMTextValidator.MAX_REPEAT_RATIO:
                return True  # Padding detectado (ex: "aaaaaaa", "0000000")

        return False

    @staticmethod
    def is_technical_identifier(text: str) -> bool:
        """
        Detecta identificadores técnicos que não devem ser traduzidos.

        Args:
            text: Texto a validar

        Returns:
            True se é identificador técnico
        """
        text = text.strip()

        # Padrões técnicos comuns
        patterns = [
            r'^[A-Z0-9_]{3,}$',           # CONST_NAME, ID_123
            r'^0x[0-9A-Fa-f]+$',          # 0xABCD
            r'^\d+$',                     # 12345
            r'^[A-Z]{1,3}\d+$',           # BTN1, LV99
            r'^.*\.(exe|dll|dat|bin)$',   # arquivo.exe
            r'^[/\\].*',                  # /path ou \path
        ]

        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def has_sufficient_words(text: str) -> bool:
        """
        Verifica se texto contém palavras reais.

        Args:
            text: Texto a validar

        Returns:
            True se contém pelo menos 1 palavra real
        """
        # Remove códigos de controle
        clean_text = text
        for code in ROMTextValidator.CONTROL_CODES:
            clean_text = clean_text.replace(code, ' ')

        # Extrai palavras (sequências de 2+ letras)
        words = re.findall(r'[a-zA-Z]{2,}', clean_text)

        # COMMERCIAL GRADE: Reject garbage sequences like "ABC", "XYZ", "JKL"
        # Words must have at least 1 vowel to be considered valid
        vowels = 'aeiouAEIOU'
        valid_words = [w for w in words if any(c in vowels for c in w)]

        # Precisa de pelo menos 1 palavra válida (com vogal)
        return len(valid_words) >= 1

    @staticmethod
    def is_translatable(text: str) -> Tuple[bool, str]:
        """
        Determina se texto é traduzível.

        Args:
            text: Texto a validar

        Returns:
            Tuple (is_translatable, reason)
        """
        if not text or not text.strip():
            return False, "EMPTY"

        # FILTRO 1: Códigos de controle puros
        if ROMTextValidator.is_control_code_heavy(text):
            return False, "CONTROL_CODES"

        # FILTRO 2: Identificadores técnicos
        if ROMTextValidator.is_technical_identifier(text):
            return False, "TECHNICAL_ID"

        # FILTRO 3: Lixo binário
        if ROMTextValidator.is_binary_garbage(text):
            return False, "BINARY_GARBAGE"

        # FILTRO 4: Sem palavras reais
        if not ROMTextValidator.has_sufficient_words(text):
            return False, "NO_WORDS"

        # Aprovado: parece texto humano real
        return True, "OK"

    @staticmethod
    def sanitize_for_translation(text: str) -> str:
        """
        Prepara texto para tradução preservando códigos de controle.

        Args:
            text: Texto original

        Returns:
            Texto sanitizado
        """
        # Normaliza espaços, mas preserva códigos
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()

        return text

    @staticmethod
    def validate_translation(original: str, translation: str) -> Tuple[bool, str]:
        """
        Valida se tradução preservou códigos de controle.

        Args:
            original: Texto original
            translation: Tradução

        Returns:
            Tuple (is_valid, reason)
        """
        if not translation or translation is None:
            return False, "TRANSLATION_IS_NONE"

        # Verifica se códigos de controle foram preservados
        for code in ROMTextValidator.CONTROL_CODES:
            original_count = original.count(code)
            translation_count = translation.count(code)

            if original_count != translation_count:
                return False, f"MISSING_CODE_{code}"

        # Verifica se comprimento não explodiu (limite +50%)
        max_length = int(len(original) * 1.5)
        if len(translation) > max_length:
            return False, "LENGTH_EXCEEDED"

        return True, "OK"


def main():
    """CLI para testar validador."""
    test_cases = [
        # (texto, esperado_traduzível)
        ("Hello world!", True),
        ("Press START", True),
        ("Player {PLAYER} found {ITEM}!", True),
        ("<0A><0D><FF>", False),  # Apenas códigos
        ("0x1234", False),  # Hexadecimal
        ("BTN_01", False),  # ID técnico
        ("aaaaaaaaaa", False),  # Padding
        ("\x00\x01\x02", False),  # Binário
        ("", False),  # Vazio
        ("A", False),  # Curto demais
        ("Game Over", True),
        ("LV99", False),  # Técnico
        ("Mario", True),
        ("data.bin", False),  # Arquivo
    ]

    validator = ROMTextValidator()

    print("=" * 60)
    print("ROM TEXT VALIDATOR - TESTES")
    print("=" * 60)

    correct = 0
    total = len(test_cases)

    for text, expected in test_cases:
        is_translatable, reason = validator.is_translatable(text)

        status = "✅" if is_translatable == expected else "❌"
        correct += 1 if is_translatable == expected else 0

        print(f"{status} '{text[:30]}' → {is_translatable} ({reason})")

    print("=" * 60)
    print(f"Acurácia: {correct}/{total} ({100*correct/total:.1f}%)")
    print("=" * 60)


if __name__ == '__main__':
    main()
