# UPDATED FUNCTION FOR: interface_tradutor_final.py

def validate_and_fix_translation(original: str, translated: str) -> str:
    """
    Aggressive chat filter for LLM translations.
    Strips conversational prefixes and detects refusals.

    Args:
        original: Original text
        translated: LLM translation

    Returns:
        Cleaned translation (fallback to original if garbage)
    """
    import re

    if not translated or translated is None:
        return original

    original_text = translated
    translated = translated.strip()

    # === STEP 1: QUOTE REMOVAL ===
    # Remove leading/trailing quotes that LLMs often add
    if translated.startswith('"') and translated.endswith('"'):
        translated = translated[1:-1].strip()
    if translated.startswith("'") and translated.endswith("'"):
        translated = translated[1:-1].strip()
    if translated.startswith('«') and translated.endswith('»'):
        translated = translated[1:-1].strip()

    # === STEP 2: BLACKLIST PREFIX FILTER ===
    # Portuguese chatty prefixes
    portuguese_prefixes = [
        'a tradução',
        'aqui está',
        'o texto',
        'traduzido',
        'segue',
        'resultado',
        'tradução:',
        'texto traduzido',
        'em português',
        'ficaria',
        'seria',
        'pode ser traduzido como',
    ]

    # English chatty prefixes
    english_prefixes = [
        'the translation',
        'here is',
        'here\'s',
        'translated',
        'this translates to',
        'this would be',
        'translation:',
        'output:',
        'result:',
    ]

    all_prefixes = portuguese_prefixes + english_prefixes

    # Check if translation starts with blacklisted phrase
    translated_lower = translated.lower()

    for prefix in all_prefixes:
        if translated_lower.startswith(prefix):
            # Found chatty prefix - try to extract actual translation

            # Look for colon separator
            if ':' in translated:
                # Split at first colon and take the part after
                parts = translated.split(':', 1)
                if len(parts) == 2 and parts[1].strip():
                    translated = parts[1].strip()
                    # Remove quotes again if present after colon
                    if translated.startswith('"') and translated.endswith('"'):
                        translated = translated[1:-1].strip()
                    break

            # No colon found - try to remove just the prefix
            # (case-insensitive removal)
            pattern = re.escape(prefix)
            translated = re.sub(f'^{pattern}', '', translated, flags=re.IGNORECASE).strip()
            break

    # === STEP 3: REFUSAL DETECTION (HARD FALLBACK) ===
    refusal_keywords = [
        # Portuguese refusals
        'não é possível',
        'não posso',
        'não consigo',
        'desculpe',
        'lamento',
        'não foi possível',
        'impossível traduzir',
        'não há tradução',

        # English refusals
        'cannot',
        'can\'t',
        'unable',
        'impossible',
        'i\'m sorry',
        'i apologize',
        'as an ai',
        'as a language model',
        'i\'m afraid',
        'inappropriate',
        'offensive',
        'harmful',
    ]

    translated_lower = translated.lower()

    for keyword in refusal_keywords:
        if keyword in translated_lower:
            # REFUSAL DETECTED - return original English
            print(f"[REFUSAL FILTER] Detected '{keyword}' - using original")
            return original

    # === STEP 4: LENGTH SANITY CHECK ===
    # If translation is >3x longer than original, it's probably garbage/explanation
    if len(translated) > len(original) * 3:
        print(f"[LENGTH FILTER] Translation too long ({len(translated)} vs {len(original)}) - using original")
        return original

    # === STEP 5: EMPTY CHECK ===
    if not translated or len(translated) < 1:
        print(f"[EMPTY FILTER] Translation empty - using original")
        return original

    # === STEP 6: PRESERVE CONTROL CODES ===
    # Restore any control codes that were removed
    control_codes = re.findall(r'<[0-9A-F]{2}>|\{[A-Z_]+\}|\[[A-Z_]+\]', original)

    for code in control_codes:
        original_count = original.count(code)
        translated_count = translated.count(code)

        if translated_count < original_count:
            # Code missing - append it
            missing = original_count - translated_count
            translated += (code * missing)

    # === STEP 7: METADATA LEAK DETECTION ===
    # Check for technical notes that leaked into output
    metadata_patterns = [
        'código de preservação',
        'preservation code',
        'nota técnica',
        'technical note',
        'note:',
        'observação:',
    ]

    for pattern in metadata_patterns:
        if pattern in translated_lower:
            print(f"[METADATA FILTER] Detected '{pattern}' - using original")
            return original

    # === STEP 8: FINAL VALIDATION ===
    # If we stripped so much that we're left with garbage, use original
    # Check if translation is mostly punctuation/symbols
    alpha_count = sum(1 for c in translated if c.isalpha())
    if alpha_count < len(translated) * 0.3:  # Less than 30% letters
        print(f"[ALPHA FILTER] Too few letters ({alpha_count}/{len(translated)}) - using original")
        return original

    return translated


# UPDATED FILE: core/rom_translation_prompts.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Translation Prompts - Zero-Tolerance Chat Filter
=====================================================

Ultra-strict prompts to prevent conversational output.
"""


class TranslationPrompts:
    """Generates prompts with harsh anti-chat enforcement."""

    @staticmethod
    def get_system_prompt() -> str:
        """
        System prompt with zero-tolerance for conversational output.

        Returns:
            System prompt string
        """
        return """CRITICAL SYSTEM DIRECTIVE: TRANSLATION FUNCTION MODE

YOU ARE NOT A CHATBOT. YOU ARE A TEXT PROCESSING FUNCTION.

ABSOLUTE RULES - ZERO TOLERANCE:
1. OUTPUT ONLY THE TRANSLATED TEXT - NO PREFIXES, NO SUFFIXES, NO EXPLANATIONS
2. FORBIDDEN PHRASES (WILL CAUSE SYSTEM FAILURE):
   - "A tradução é:"
   - "Aqui está:"
   - "O texto traduzido:"
   - "Não é possível:"
   - "The translation is:"
   - "Here is:"
   - ANY introductory phrase

3. FORBIDDEN BEHAVIORS:
   - Adding colons (:) before output
   - Adding quotes around output
   - Explaining what you're doing
   - Apologizing or refusing
   - Adding metadata or notes

4. IF UNTRANSLATABLE: Return the EXACT original text character-for-character
5. PRESERVE ALL CODES: <0A>, {VAR}, [NAME] etc.

CORRECT EXAMPLES:
Input: "Press START"
Output: Pressione START

Input: "Game Over"
Output: Fim de Jogo

INCORRECT EXAMPLES (SYSTEM FAILURE):
Input: "Press START"
Output: A tradução é: Pressione START ❌ FORBIDDEN
Output: "Pressione START" ❌ FORBIDDEN
Output: Aqui está o texto traduzido: Pressione START ❌ FORBIDDEN

THIS IS A TECHNICAL FUNCTION. CONVERSATIONAL OUTPUT WILL CORRUPT THE SYSTEM.

BEGIN PROCESSING MODE."""

    @staticmethod
    def get_translation_prompt(text: str, target_lang: str) -> str:
        """
        Generate ultra-strict translation prompt.

        Args:
            text: Text to translate
            target_lang: Target language

        Returns:
            Full prompt
        """
        return f"""FUNCTION CALL: translate()

PARAMETERS:
- input_text: {text}
- target_language: {target_lang}

EXECUTION MODE: DIRECT OUTPUT ONLY

CRITICAL WARNING: Any prefix, explanation, or conversational text will corrupt the system.
Output ONLY the translation. NO colons, NO quotes, NO introductions.

If translation impossible: return input_text exactly.

EXECUTE:"""

    @staticmethod
    def extract_translation(response: str, original: str) -> str:
        """
        Extract translation with aggressive chat filtering.

        Args:
            response: LLM response
            original: Original text

        Returns:
            Cleaned translation (NEVER None)
        """
        if not response or response is None:
            return original

        # Strip whitespace
        response = response.strip()

        # Remove common prefixes before colon
        if ':' in response:
            # Check if it starts with chatty phrase
            chatty_patterns = [
                r'^a tradução (é|do texto é|seria):',
                r'^aqui está:',
                r'^o texto (traduzido|em \w+ seria):',
                r'^tradução:',
                r'^resultado:',
                r'^the translation (is|would be):',
                r'^here (is|\'s):',
                r'^translation:',
                r'^output:',
            ]

            for pattern in chatty_patterns:
                if re.match(pattern, response, re.IGNORECASE):
                    # Split at colon and take part after
                    parts = response.split(':', 1)
                    if len(parts) == 2:
                        response = parts[1].strip()
                    break

        # Remove quotes
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        if response.startswith("'") and response.endswith("'"):
            response = response[1:-1]

        # Get first line only (ignore multi-line explanations)
        response = response.split('\n')[0].strip()

        # Fallback if empty
        if not response:
            return original

        return response

    @staticmethod
    def validate_and_fix_translation(original: str, translated: str) -> str:
        """
        Final validation with chat filter.

        Args:
            original: Original text
            translated: Translated text

        Returns:
            Validated translation
        """
        # Import the standalone function we defined above
        return validate_and_fix_translation(original, translated)


# COMPLETE STANDALONE validate_and_fix_translation (with import)
import re

def validate_and_fix_translation(original: str, translated: str) -> str:
    """
    Aggressive chat filter for LLM translations.
    Strips conversational prefixes and detects refusals.

    Args:
        original: Original text
        translated: LLM translation

    Returns:
        Cleaned translation (fallback to original if garbage)
    """
    if not translated or translated is None:
        return original

    original_text = translated
    translated = translated.strip()

    # STEP 1: QUOTE REMOVAL
    if translated.startswith('"') and translated.endswith('"'):
        translated = translated[1:-1].strip()
    if translated.startswith("'") and translated.endswith("'"):
        translated = translated[1:-1].strip()
    if translated.startswith('«') and translated.endswith('»'):
        translated = translated[1:-1].strip()

    # STEP 2: BLACKLIST PREFIX FILTER
    portuguese_prefixes = [
        'a tradução', 'aqui está', 'o texto', 'traduzido',
        'segue', 'resultado', 'tradução:', 'texto traduzido',
        'em português', 'ficaria', 'seria', 'pode ser traduzido como',
    ]

    english_prefixes = [
        'the translation', 'here is', 'here\'s', 'translated',
        'this translates to', 'this would be', 'translation:',
        'output:', 'result:',
    ]

    all_prefixes = portuguese_prefixes + english_prefixes
    translated_lower = translated.lower()

    for prefix in all_prefixes:
        if translated_lower.startswith(prefix):
            if ':' in translated:
                parts = translated.split(':', 1)
                if len(parts) == 2 and parts[1].strip():
                    translated = parts[1].strip()
                    if translated.startswith('"') and translated.endswith('"'):
                        translated = translated[1:-1].strip()
                    break

            pattern = re.escape(prefix)
            translated = re.sub(f'^{pattern}', '', translated, flags=re.IGNORECASE).strip()
            break

    # STEP 3: REFUSAL DETECTION
    refusal_keywords = [
        'não é possível', 'não posso', 'não consigo', 'desculpe',
        'lamento', 'não foi possível', 'impossível traduzir',
        'cannot', 'can\'t', 'unable', 'impossible', 'i\'m sorry',
        'i apologize', 'as an ai', 'inappropriate', 'offensive',
    ]

    translated_lower = translated.lower()

    for keyword in refusal_keywords:
        if keyword in translated_lower:
            print(f"[REFUSAL] '{keyword}' detected - returning original")
            return original

    # STEP 4: LENGTH SANITY CHECK
    if len(translated) > len(original) * 3:
        print(f"[LENGTH] Too long ({len(translated)} vs {len(original)}) - returning original")
        return original

    # STEP 5: EMPTY CHECK
    if not translated or len(translated) < 1:
        print(f"[EMPTY] Translation empty - returning original")
        return original

    # STEP 6: PRESERVE CONTROL CODES
    control_codes = re.findall(r'<[0-9A-F]{2}>|\{[A-Z_]+\}|\[[A-Z_]+\]', original)

    for code in control_codes:
        original_count = original.count(code)
        translated_count = translated.count(code)

        if translated_count < original_count:
            missing = original_count - translated_count
            translated += (code * missing)

    # STEP 7: METADATA LEAK DETECTION
    metadata_patterns = [
        'código de preservação', 'preservation code',
        'nota técnica', 'technical note', 'note:', 'observação:',
    ]

    for pattern in metadata_patterns:
        if pattern in translated_lower:
            print(f"[METADATA] '{pattern}' detected - returning original")
            return original

    # STEP 8: ALPHA VALIDATION
    alpha_count = sum(1 for c in translated if c.isalpha())
    if alpha_count < len(translated) * 0.3:
        print(f"[ALPHA] Too few letters ({alpha_count}/{len(translated)}) - returning original")
        return original

    return translated
