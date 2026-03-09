# -*- coding: utf-8 -*-
"""
================================================================================
LINGUISTIC QA - Auditoria Linguistica Automatica
================================================================================
Sistema de controle de qualidade linguistico para traducoes de ROM.

Funcionalidades:
- Calculo de quality_score por item (0.0-1.0)
- Verificacao de consistencia com glossario
- Verificacao de preservacao de placeholders
- Retranslacao automatica se qualidade abaixo do limiar
- Fallback para traducao literal se retranslacao falhar
================================================================================
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class LinguisticQAResult:
    """Resultado de avaliacao linguistica."""
    uid: str
    original: str
    translation: str
    quality_score: float
    passed: bool
    flags: List[str] = field(default_factory=list)
    final_translation: str = ""
    retranslation_attempts: int = 0

    def __post_init__(self):
        if not self.final_translation:
            self.final_translation = self.translation

    def to_dict(self) -> dict:
        return {
            'uid': self.uid,
            'quality_score': round(self.quality_score, 4),
            'passed': self.passed,
            'flags': self.flags,
            'retranslation_attempts': self.retranslation_attempts,
            'used_final': self.final_translation != self.translation
        }


class LinguisticQA:
    """
    Sistema de QA linguistico para traducoes de ROM.

    Avalia qualidade de traducoes e pode retraduzir automaticamente
    se a qualidade estiver abaixo do limiar.
    """

    # Glossario padrao para jogos retro
    DEFAULT_GLOSSARY = {
        # Termos comuns que devem ser consistentes
        'HP': 'PV',
        'MP': 'PM',
        'EXP': 'EXP',
        'LV': 'NV',
        'ATK': 'ATQ',
        'DEF': 'DEF',
        'STR': 'FOR',
        'INT': 'INT',
        'AGI': 'AGI',
        'GAME OVER': 'FIM DE JOGO',
        'CONTINUE': 'CONTINUAR',
        'START': 'INICIAR',
        'SAVE': 'SALVAR',
        'LOAD': 'CARREGAR',
    }

    # Nomes proprios que NAO devem ser traduzidos
    PROPER_NOUNS_PATTERN = re.compile(
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    )

    def __init__(
        self,
        glossary_path: Optional[str] = None,
        min_quality: float = 0.7,
        glossary: Optional[Dict[str, str]] = None
    ):
        """
        Inicializa QA linguistico.

        Args:
            glossary_path: Caminho para arquivo JSON de glossario
            min_quality: Score minimo para passar (0.0-1.0)
            glossary: Glossario direto (override de glossary_path)
        """
        self.min_quality = min_quality
        self.glossary = glossary or self._load_glossary(glossary_path)
        self.translator: Optional[Callable[[str], str]] = None
        self.strict_translator: Optional[Callable[[str, Dict], str]] = None

    def _load_glossary(self, path: Optional[str]) -> Dict[str, str]:
        """Carrega glossario de arquivo ou usa default."""
        if path:
            try:
                p = Path(path)
                if p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Suporta formato {"terms": {...}} ou direto
                        return data.get('terms', data)
            except Exception:
                pass

        return self.DEFAULT_GLOSSARY.copy()

    def set_translator(
        self,
        translator: Callable[[str], str],
        strict_translator: Optional[Callable[[str, Dict], str]] = None
    ):
        """
        Define funcao de traducao para retranslacao automatica.

        Args:
            translator: Funcao que recebe texto e retorna traducao
            strict_translator: Funcao com hints adicionais (glossario, etc)
        """
        self.translator = translator
        self.strict_translator = strict_translator

    def assess(
        self,
        uid: str,
        original: str,
        translation: str
    ) -> LinguisticQAResult:
        """
        Avalia qualidade de uma traducao.

        Args:
            uid: Identificador unico do item
            original: Texto original
            translation: Texto traduzido

        Returns:
            LinguisticQAResult com score e flags
        """
        score = 1.0
        flags = []

        # Check 1: Consistencia com glossario
        glossary_score, glossary_flags = self._check_glossary(original, translation)
        score -= (1.0 - glossary_score) * 0.3  # Peso 30%
        flags.extend(glossary_flags)

        # Check 2: Placeholders preservados
        ph_score, ph_flags = self._check_placeholders(original, translation)
        score -= (1.0 - ph_score) * 0.3  # Peso 30%
        flags.extend(ph_flags)

        # Check 3: Nomes proprios preservados
        names_score, names_flags = self._check_proper_nouns(original, translation)
        score -= (1.0 - names_score) * 0.2  # Peso 20%
        flags.extend(names_flags)

        # Check 4: Pontuacao coerente
        punct_score, punct_flags = self._check_punctuation(original, translation)
        score -= (1.0 - punct_score) * 0.1  # Peso 10%
        flags.extend(punct_flags)

        # Check 5: Comprimento razoavel
        len_score, len_flags = self._check_length(original, translation)
        score -= (1.0 - len_score) * 0.1  # Peso 10%
        flags.extend(len_flags)

        # Normaliza score
        score = max(0.0, min(1.0, score))

        return LinguisticQAResult(
            uid=uid,
            original=original,
            translation=translation,
            quality_score=score,
            passed=score >= self.min_quality,
            flags=flags,
            final_translation=translation
        )

    def _check_glossary(
        self,
        original: str,
        translation: str
    ) -> Tuple[float, List[str]]:
        """Verifica consistencia com glossario."""
        flags = []
        matches = 0
        total = 0

        orig_upper = original.upper()
        trans_upper = translation.upper()

        for term, expected in self.glossary.items():
            if term.upper() in orig_upper:
                total += 1
                if expected.upper() in trans_upper:
                    matches += 1
                else:
                    flags.append(f"glossary_miss:{term}->{expected}")

        if total == 0:
            return 1.0, flags

        return matches / total, flags

    def _check_placeholders(
        self,
        original: str,
        translation: str
    ) -> Tuple[float, List[str]]:
        """Verifica preservacao de placeholders."""
        flags = []
        patterns = [
            r'\{[^}]+\}',           # {name}
            r'%[0-9]*[sdxX]',       # %s, %d
            r'<[0-9A-Fa-f]{2}>',    # <00>
            r'\$[A-Z_]+',           # $VAR
        ]

        combined = re.compile('|'.join(patterns))
        orig_ph = combined.findall(original)
        trans_ph = combined.findall(translation)

        if not orig_ph:
            return 1.0, flags

        # Conta matches
        from collections import Counter
        orig_counts = Counter(orig_ph)
        trans_counts = Counter(trans_ph)

        missing = 0
        for ph, count in orig_counts.items():
            diff = count - trans_counts.get(ph, 0)
            if diff > 0:
                missing += diff
                flags.append(f"placeholder_missing:{ph}")

        score = max(0.0, 1.0 - (missing / len(orig_ph)))
        return score, flags

    def _check_proper_nouns(
        self,
        original: str,
        translation: str
    ) -> Tuple[float, List[str]]:
        """Verifica preservacao de nomes proprios."""
        flags = []

        # Encontra nomes proprios no original
        names = self.PROPER_NOUNS_PATTERN.findall(original)

        # Filtra palavras comuns em ingles que nao sao nomes
        common_words = {
            'The', 'This', 'That', 'What', 'Where', 'When', 'Why', 'How',
            'You', 'Your', 'Are', 'Can', 'Will', 'Would', 'Could', 'Should',
            'Have', 'Has', 'Had', 'Been', 'Being', 'Was', 'Were', 'Did',
            'Press', 'Start', 'Game', 'Over', 'Continue', 'Save', 'Load'
        }
        names = [n for n in names if n not in common_words]

        if not names:
            return 1.0, flags

        # Verifica se nomes aparecem na traducao
        preserved = sum(1 for n in names if n in translation)
        score = preserved / len(names)

        for name in names:
            if name not in translation:
                flags.append(f"proper_noun_changed:{name}")

        return score, flags

    def _check_punctuation(
        self,
        original: str,
        translation: str
    ) -> Tuple[float, List[str]]:
        """Verifica coerencia de pontuacao."""
        flags = []

        # Verifica se termina com mesmo tipo de pontuacao
        orig_end = original.strip()[-1] if original.strip() else ''
        trans_end = translation.strip()[-1] if translation.strip() else ''

        # Mapeamento de pontuacao equivalente
        punct_map = {
            '?': '?', '!': '!', '.': '.', ':': ':',
            '...': '...', '…': '...'
        }

        score = 1.0
        if orig_end in punct_map:
            expected = punct_map[orig_end]
            if trans_end != expected and trans_end not in punct_map:
                score = 0.5
                flags.append(f"punctuation_mismatch:{orig_end}->{trans_end}")

        return score, flags

    def _check_length(
        self,
        original: str,
        translation: str
    ) -> Tuple[float, List[str]]:
        """Verifica se comprimento e razoavel."""
        flags = []

        if not original:
            return 1.0, flags

        ratio = len(translation) / len(original)

        # Portugues tende a ser 10-30% mais longo que ingles
        if ratio < 0.5:
            flags.append(f"too_short:{ratio:.2f}x")
            return 0.5, flags
        elif ratio > 3.0:
            flags.append(f"too_long:{ratio:.2f}x")
            return 0.7, flags

        return 1.0, flags

    def assess_with_retry(
        self,
        uid: str,
        original: str,
        translation: str,
        max_retries: int = 1
    ) -> LinguisticQAResult:
        """
        Avalia e retraduz automaticamente se falhar.

        Args:
            uid: Identificador do item
            original: Texto original
            translation: Traducao inicial
            max_retries: Numero maximo de tentativas de retraducao

        Returns:
            LinguisticQAResult com traducao final (pode ser retraduzida)
        """
        result = self.assess(uid, original, translation)

        if result.passed or not self.translator:
            return result

        # Tenta retraducao
        for attempt in range(max_retries):
            result.retranslation_attempts += 1

            try:
                # Usa tradutor estrito se disponivel
                if self.strict_translator:
                    hints = {
                        'glossary': self.glossary,
                        'flags': result.flags,
                        'preserve_names': True
                    }
                    new_trans = self.strict_translator(original, hints)
                else:
                    new_trans = self.translator(original)

                # Reavalia
                new_result = self.assess(uid, original, new_trans)

                if new_result.passed:
                    new_result.retranslation_attempts = result.retranslation_attempts
                    new_result.flags.append("retranslation_success")
                    return new_result

                result = new_result

            except Exception as e:
                result.flags.append(f"retranslation_error:{str(e)[:50]}")

        # Fallback: traducao mais literal
        result.final_translation = self._literal_fallback(original, translation)
        result.flags.append("used_literal_fallback")

        return result

    def _literal_fallback(self, original: str, translation: str) -> str:
        """
        Gera traducao mais literal como fallback.

        Preserva placeholders e tokens do original, traduz apenas palavras.
        """
        # Se traducao e muito diferente, usa original com marcacao
        if not translation or len(translation) < len(original) * 0.3:
            return f"[{original}]"

        # Preserva tokens do original na traducao
        token_pattern = re.compile(r'<[^>]+>|\{[^}]+\}|%[sdxX]|\$[A-Z_]+')
        orig_tokens = token_pattern.findall(original)

        result = translation
        for token in orig_tokens:
            if token not in result:
                # Adiciona token no final se faltando
                result = result.rstrip() + ' ' + token

        return result

    def batch_assess(
        self,
        items: List[Tuple[str, str, str]],
        with_retry: bool = False,
        max_retries: int = 1
    ) -> List[LinguisticQAResult]:
        """
        Avalia lote de traducoes.

        Args:
            items: Lista de (uid, original, translation)
            with_retry: Se deve tentar retraducao automatica
            max_retries: Numero maximo de retentativas

        Returns:
            Lista de LinguisticQAResult
        """
        results = []

        for uid, original, translation in items:
            if with_retry:
                result = self.assess_with_retry(uid, original, translation, max_retries)
            else:
                result = self.assess(uid, original, translation)
            results.append(result)

        return results

    def get_summary(self, results: List[LinguisticQAResult]) -> Dict[str, Any]:
        """
        Gera sumario de resultados de QA.

        Args:
            results: Lista de resultados

        Returns:
            Dicionario com estatisticas
        """
        if not results:
            return {'total': 0}

        passed = sum(1 for r in results if r.passed)
        avg_score = sum(r.quality_score for r in results) / len(results)
        retranslations = sum(1 for r in results if r.retranslation_attempts > 0)
        fallbacks = sum(1 for r in results if 'used_literal_fallback' in r.flags)

        # Conta flags mais comuns
        from collections import Counter
        all_flags = []
        for r in results:
            all_flags.extend(r.flags)
        common_flags = Counter(all_flags).most_common(10)

        return {
            'total': len(results),
            'passed': passed,
            'failed': len(results) - passed,
            'pass_rate': passed / len(results),
            'average_score': round(avg_score, 4),
            'retranslations': retranslations,
            'fallbacks': fallbacks,
            'common_issues': common_flags
        }


def create_linguistic_qa(
    glossary_path: Optional[str] = None,
    min_quality: float = 0.7
) -> LinguisticQA:
    """
    Factory function para criar instancia de QA.

    Args:
        glossary_path: Caminho para glossario
        min_quality: Score minimo

    Returns:
        LinguisticQA configurado
    """
    return LinguisticQA(glossary_path=glossary_path, min_quality=min_quality)
