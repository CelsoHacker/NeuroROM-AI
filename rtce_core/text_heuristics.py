# -*- coding: utf-8 -*-
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class TextType(Enum):
    LETTER = "letter"
    WORD = "word"
    PHRASE = "phrase"
    MENU_STRING = "menu_string"
    GARBAGE = "garbage"

@dataclass
class TextCandidate:
    text: str
    offset: int
    text_type: TextType
    confidence: float
    metrics: Dict

class TextHeuristics:
    MIN_STRING_LENGTH = 3
    MAX_STRING_LENGTH = 128
    VOWELS = set('aeiouAEIOUáéíóúâêôãõyY')
    GAME_KEYWORDS = {'start', 'continue', 'options', 'exit', 'quit', 'save', 'load', 'yes', 'no', 'menu'}

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        if not data: return 0.0
        freq = {b: data.count(b) for b in set(data)}
        entropy = 0.0
        for count in freq.values():
            p = count / len(data)
            entropy -= p * math.log2(p)
        return entropy

    def analyze_string(self, data: bytes, offset: int = 0, encoding: str = 'ascii') -> Optional[TextCandidate]:
        try:
            text = data.decode(encoding, errors='ignore').strip('\x00').strip()
            if len(text) < self.MIN_STRING_LENGTH: return None

            letters = [c for c in text if c.isalpha()]
            if not letters: return None

            v_count = sum(1 for c in letters if c in self.VOWELS)
            v_ratio = v_count / len(letters)

            # Filtro: Texto humano geralmente tem entre 25% e 65% de vogais
            confidence = 1.0 if 0.25 <= v_ratio <= 0.65 else 0.4

            t_type = TextType.PHRASE if ' ' in text else TextType.WORD
            if text.lower() in self.GAME_KEYWORDS: t_type = TextType.MENU_STRING

            return TextCandidate(text, offset, t_type, confidence, {"v_ratio": v_ratio})
        except:
            return None

    def scan_memory_for_strings(self, data: bytes, base_offset: int = 0, encoding: str = 'ascii'):
        candidates = []
        # Busca básica por sequências de bytes imprimíveis
        chunks = re.finditer(rb'[ -~]{3,}', data)
        for match in chunks:
            cand = self.analyze_string(match.group(), base_offset + match.start(), encoding)
            if cand and cand.confidence > 0.5:
                candidates.append(cand)
        return candidates