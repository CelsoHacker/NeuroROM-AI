# -*- coding: utf-8 -*-
"""
Gate semântico rígido para tradução de ROM.

Objetivo:
- Bloquear deriva semântica, alucinação e expansão indevida.
- Forçar obediência a glossário e proteção de nomes próprios.
- Aplicar política única de registro (tu/você/cê).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Tuple


PLACEHOLDER_RE = re.compile(
    r"(<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>|%\d*[dsxX]|\{[A-Za-z0-9_:-]+\}|\[[A-Za-z0-9_:-]+\]|@[A-Za-z0-9_]+)"
)
TITLE_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.'-]{1,}")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]+")
UPPER_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")
NUMBER_RE = re.compile(r"\b\d+\b")


def _strip_accents(text: str) -> str:
    raw = str(text or "")
    nfd = unicodedata.normalize("NFD", raw)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _canon(text: str) -> str:
    compact = _strip_accents(str(text or "")).casefold()
    return re.sub(r"\s+", " ", compact).strip()


def _tokens(text: str) -> List[str]:
    return [tok for tok in WORD_RE.findall(str(text or "")) if tok]


class SemanticQualityGate:
    DEFAULT_REGISTER_POLICY = "voce"
    REGISTER_ALIASES = {
        "voce": "voce",
        "você": "voce",
        "vc": "voce",
        "tu": "tu",
        "ce": "ce",
        "cê": "ce",
    }
    REGISTER_MARKERS = {
        "tu": {
            "tu",
            "teu",
            "tua",
            "tens",
            "contigo",
            "estas",
            "estás",
            "foste",
            "podes",
            "vais",
        },
        "voce": {
            "voce",
            "você",
            "voces",
            "vocês",
            "seu",
            "sua",
            "seus",
            "suas",
            "senhor",
            "senhora",
        },
        "ce": {
            "ce",
            "cê",
        },
    }
    STRONG_FLAGS = (
        "semantic_hallucination_suspect",
        "glossary_violation",
        "proper_noun_corruption",
        "register_inconsistency",
        "semantic_drift",
    )
    HALLUCINATION_MARKERS = (
        "bairro de",
        "cidade de",
        "capital",
        "ou seja",
        "isto e",
        "isso e",
        "significa",
        "explicacao",
        "explica",
        "londres",
        "inglaterra",
    )
    PROPER_NOUN_STOPWORDS = {
        "The",
        "This",
        "That",
        "When",
        "Where",
        "What",
        "You",
        "Your",
        "Press",
        "Start",
        "Load",
        "Save",
        "Game",
        "Menu",
        "Continue",
    }
    TITLE_CONNECTORS = {"the", "of", "de", "da", "do", "dos", "das", "del", "la"}
    COMMON_NON_PROPER_TITLE_WORDS = {
        "Aim",
        "All",
        "Any",
        "Are",
        "Armour",
        "Attack",
        "Attacked",
        "Book",
        "But",
        "Candle",
        "Command",
        "Combat",
        "Dead",
        "Direction",
        "Disabled",
        "Dungeon",
        "East",
        "Energy",
        "Equipment",
        "Exit",
        "Female",
        "Find",
        "Flame",
        "Green",
        "Hello",
        "Here",
        "How",
        "Interest",
        "Item",
        "Items",
        "Key",
        "Killed",
        "Level",
        "Locate",
        "Magic",
        "Male",
        "Mandrake",
        "Map",
        "Name",
        "New",
        "Nightshade",
        "North",
        "Not",
        "Only",
        "Orange",
        "Phase",
        "Player",
        "Poisoned",
        "Purple",
        "Ready",
        "Reagents",
        "Room",
        "Runes",
        "See",
        "Sleep",
        "Slow",
        "South",
        "Spell",
        "Start",
        "Stone",
        "Stones",
        "Sword",
        "Thank",
        "Torch",
        "Torches",
        "Travel",
        "Use",
        "Weapon",
        "West",
        "Wheel",
        "Who",
        "Wrong",
        "Yes",
    }
    EN_COMMON = {
        "the",
        "and",
        "with",
        "from",
        "your",
        "you",
        "open",
        "door",
        "start",
        "continue",
        "load",
        "save",
        "press",
        "attack",
        "magic",
        "item",
    }
    PT_COMMON = {
        "de",
        "da",
        "do",
        "dos",
        "das",
        "para",
        "com",
        "por",
        "em",
        "no",
        "na",
        "os",
        "as",
        "um",
            "uma",
            "que",
            "se",
            "usar",
            "item",
            "itens",
            "magia",
            "chave",
            "gema",
            "jogador",
            "interesse",
            "incenso",
            "voce",
            "você",
            "tu",
    }
    DEFAULT_GLOSSARY: Dict[str, Dict[str, Any]] = {
        # Virtudes
        "Honesty": {"target": "Honestidade", "category": "virtue", "preserve": False},
        "Compassion": {"target": "Compaixão", "category": "virtue", "preserve": False},
        "Valor": {"target": "Valor", "category": "virtue", "preserve": False},
        "Justice": {"target": "Justiça", "category": "virtue", "preserve": False},
        "Sacrifice": {"target": "Sacrifício", "category": "virtue", "preserve": False},
        "Honor": {"target": "Honra", "category": "virtue", "preserve": False},
        "Spirituality": {"target": "Espiritualidade", "category": "virtue", "preserve": False},
        "Humility": {"target": "Humildade", "category": "virtue", "preserve": False},
        # Cidades / locais
        "Britain": {"target": "Britain", "category": "city", "preserve": True},
        "Moonglow": {"target": "Moonglow", "category": "city", "preserve": True},
        "Yew": {"target": "Yew", "category": "city", "preserve": True},
        "Minoc": {"target": "Minoc", "category": "city", "preserve": True},
        "Trinsic": {"target": "Trinsic", "category": "city", "preserve": True},
        "Skara Brae": {"target": "Skara Brae", "category": "city", "preserve": True},
        "Jhelom": {"target": "Jhelom", "category": "city", "preserve": True},
        "New Magincia": {"target": "New Magincia", "category": "city", "preserve": True},
        # Termos de UI recorrentes
        "HP": {"target": "PV", "category": "interface", "preserve": False},
        "MP": {"target": "PM", "category": "interface", "preserve": False},
        "EXP": {"target": "EXP", "category": "interface", "preserve": False},
        "LV": {"target": "NV", "category": "interface", "preserve": False},
        "START": {"target": "INICIAR", "category": "interface", "preserve": False},
        "SAVE": {"target": "SALVAR", "category": "interface", "preserve": False},
        "LOAD": {"target": "CARREGAR", "category": "interface", "preserve": False},
        "CONTINUE": {"target": "CONTINUAR", "category": "interface", "preserve": False},
    }

    def __init__(
        self,
        glossary: Optional[Mapping[str, Any]] = None,
        register_policy: str = DEFAULT_REGISTER_POLICY,
        strict_mode: bool = False,
        min_semantic_score_standard: float = 70.0,
        min_semantic_score_strict: float = 82.0,
    ) -> None:
        self.glossary = self._normalize_glossary(glossary)
        self.register_policy = self._normalize_register_policy(register_policy)
        self.strict_mode = bool(strict_mode)
        self.min_semantic_score_standard = float(min_semantic_score_standard)
        self.min_semantic_score_strict = float(min_semantic_score_strict)

    def _normalize_register_policy(self, value: str) -> str:
        key = str(value or "").strip().casefold()
        return self.REGISTER_ALIASES.get(key, self.DEFAULT_REGISTER_POLICY)

    def _normalize_glossary(self, glossary: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}

        def _add_entry(src_term: str, payload: Any) -> None:
            src = str(src_term or "").strip()
            if not src:
                return
            if isinstance(payload, dict):
                target = str(payload.get("target", payload.get("translation", src)) or src).strip()
                category = str(payload.get("category", "term") or "term").strip().lower()
                preserve = bool(payload.get("preserve", False))
                allow_translation = bool(payload.get("allow_translation", not preserve))
                enforce = bool(payload.get("enforce", True))
            else:
                target = str(payload or src).strip() or src
                category = "term"
                preserve = False
                allow_translation = True
                enforce = True
            normalized[src] = {
                "target": target,
                "category": category,
                "preserve": preserve,
                "allow_translation": allow_translation,
                "enforce": enforce,
            }

        for term, payload in self.DEFAULT_GLOSSARY.items():
            if isinstance(payload, dict):
                base_payload = dict(payload)
                base_payload.setdefault("enforce", False)
                _add_entry(term, base_payload)
            else:
                _add_entry(term, payload)

        if isinstance(glossary, Mapping):
            for term, payload in glossary.items():
                _add_entry(str(term), payload)

        return normalized

    def _semantic_threshold_used(self) -> float:
        if self.strict_mode:
            return float(self.min_semantic_score_strict)
        return float(self.min_semantic_score_standard)

    def _glossary_check(self, source: str, translated: str) -> Tuple[List[str], List[str]]:
        src_canon = _canon(source)
        dst_canon = _canon(translated)
        hits: List[str] = []
        violations: List[str] = []
        for src_term, rule in self.glossary.items():
            src_term_canon = _canon(src_term)
            if not src_term_canon or src_term_canon not in src_canon:
                continue
            hits.append(src_term)
            expected = str(rule.get("target", src_term) or src_term)
            preserve = bool(rule.get("preserve", False))
            allow_translation = bool(rule.get("allow_translation", not preserve))
            expected_token = src_term if preserve and not allow_translation else expected
            if _canon(expected_token) not in dst_canon:
                if not bool(rule.get("enforce", True)):
                    continue
                # Para siglas curtas de interface (HP/MP/LV), aceitamos
                # preservação literal quando houver política explícita de troca.
                if src_term.isupper() and len(src_term) <= 4 and _canon(src_term) in dst_canon:
                    continue
                violations.append(f"{src_term}->{expected_token}")
        return hits, violations

    def _proper_nouns_from_source(self, source: str) -> List[str]:
        out: List[str] = []
        text = str(source or "")
        tokens = TITLE_TOKEN_RE.findall(text)

        for idx, token in enumerate(tokens):
            if not token or not token[0].isupper():
                continue
            if token in self.PROPER_NOUN_STOPWORDS:
                continue
            # Evita tratar texto genérico em caixa alta como nome próprio.
            if token.isupper() and "." not in token and "-" not in token:
                continue

            token_low = token.casefold()
            prev_tok = tokens[idx - 1] if idx > 0 else ""
            next_tok = tokens[idx + 1] if (idx + 1) < len(tokens) else ""
            prev_low = prev_tok.casefold()
            next_low = next_tok.casefold()
            next2_tok = tokens[idx + 2] if (idx + 2) < len(tokens) else ""
            next2_cap = bool(next2_tok and next2_tok[0].isupper())

            has_symbol = any(ch in token for ch in "._'-")
            has_digit_inside = any(ch.isdigit() for ch in token[1:])
            has_inner_upper = any(ch.isupper() for ch in token[1:])
            next_cap = bool(next_tok and next_tok[0].isupper())
            prev_cap = bool(prev_tok and prev_tok[0].isupper())
            in_title_chain = bool(next_cap or prev_cap)
            connector_chain = bool(next_low in self.TITLE_CONNECTORS and next2_cap)

            # Regra conservadora: só assume nome próprio sem glossário quando há
            # padrão forte (cadeia de título/camel/símbolo/conector).
            likely_name = bool(
                has_symbol or has_digit_inside or has_inner_upper or in_title_chain or connector_chain
            )
            if not likely_name:
                continue
            if token in self.COMMON_NON_PROPER_TITLE_WORDS:
                continue
            if token not in out:
                out.append(token)
        for term, rule in self.glossary.items():
            category = str(rule.get("category", "") or "").lower()
            if category in {"proper_noun", "city", "npc", "item", "spell", "class", "location", "virtue"}:
                if _canon(term) in _canon(source) and term not in out:
                    out.append(term)
        return out

    def _proper_noun_check(self, source: str, translated: str) -> Tuple[List[str], List[str]]:
        src_names = self._proper_nouns_from_source(source)
        dst_canon = _canon(translated)
        hits: List[str] = []
        preserved: List[str] = []
        for name in src_names:
            hits.append(name)
            rule = self.glossary.get(name, {})
            preserve = bool(rule.get("preserve", True))
            allow_translation = bool(rule.get("allow_translation", not preserve))
            expected = str(rule.get("target", name) or name)
            expected_token = name if preserve and not allow_translation else expected
            if _canon(expected_token) in dst_canon:
                preserved.append(name)
        return hits, preserved

    def _register_check(self, translated: str) -> Tuple[bool, Dict[str, int]]:
        low = _canon(translated)
        words = set(_tokens(low))
        families: Dict[str, int] = {}
        for family, markers in self.REGISTER_MARKERS.items():
            hits = sum(1 for marker in markers if marker in words)
            if hits > 0:
                families[family] = hits
        if not families:
            return False, {}
        active = set(families.keys())
        if len(active) > 1:
            return True, families
        policy = self.register_policy
        if policy not in active:
            return True, families
        return False, families

    def _semantic_drift_check(self, source: str, translated: str) -> bool:
        src_ph = Counter(PLACEHOLDER_RE.findall(str(source or "")))
        dst_ph = Counter(PLACEHOLDER_RE.findall(str(translated or "")))
        if src_ph != dst_ph:
            return True
        src_num = Counter(NUMBER_RE.findall(str(source or "")))
        dst_num = Counter(NUMBER_RE.findall(str(translated or "")))
        if src_num != dst_num:
            return True
        src_acr = []
        ui_acronyms = {"HP", "MP", "LV", "EXP", "STR", "DEF", "ATK", "INT", "AGI", "SP"}
        for tok in UPPER_ACRONYM_RE.findall(str(source or "")):
            if tok in {"I"}:
                continue
            # Só força siglas da UI/glossário. Evita bloquear tradução de
            # palavras comuns em caixa alta (ex: BYE, HELLO).
            if tok in ui_acronyms or tok in self.glossary:
                src_acr.append(tok)
        dst_canon = _canon(translated)
        glossary_by_canon = {_canon(key): value for key, value in self.glossary.items()}
        for acr in src_acr:
            alternatives = {_canon(acr)}
            rule = glossary_by_canon.get(_canon(acr))
            if isinstance(rule, dict):
                preserve = bool(rule.get("preserve", False))
                allow_translation = bool(rule.get("allow_translation", not preserve))
                target = str(rule.get("target", acr) or acr).strip() or acr
                expected = acr if preserve and not allow_translation else target
                alternatives.add(_canon(expected))
            if not any(alt and alt in dst_canon for alt in alternatives):
                return True
        return False

    def _fragment_check(self, translated: str) -> bool:
        dst = str(translated or "").strip()
        if not dst:
            return True
        words = _tokens(dst)
        if len(words) == 0:
            return True
        if dst[0] in {",", ".", ";", ":", "!", "?"}:
            return True
        if len(words) >= 2 and len(words[-1]) <= 1:
            return True
        return False

    def _english_residue_check(self, source: str, translated: str) -> bool:
        clean_src = PLACEHOLDER_RE.sub(" ", str(source or ""))
        clean_dst = PLACEHOLDER_RE.sub(" ", str(translated or ""))
        words = [w.casefold() for w in _tokens(clean_dst)]
        content_words = [w for w in words if len(w) >= 3 and not w.isdigit()]
        if not content_words:
            return False
        en_hits = sum(1 for w in content_words if w in self.EN_COMMON)
        pt_hits = sum(1 for w in content_words if w in self.PT_COMMON)
        if en_hits >= 1 and pt_hits == 0 and len(content_words) >= 2:
            return True
        src_canon = _canon(clean_src)
        dst_canon = _canon(clean_dst)
        if src_canon and src_canon == dst_canon and len(content_words) >= 2:
            if any(w in self.EN_COMMON for w in content_words) and all(
                all(ord(ch) < 128 for ch in token) for token in content_words
            ):
                return True
        return False

    def _hallucination_check(self, source: str, translated: str) -> bool:
        src_canon = _canon(source)
        dst_canon = _canon(translated)
        for marker in self.HALLUCINATION_MARKERS:
            marker_norm = _canon(marker)
            if not marker_norm:
                continue
            marker_re = re.compile(rf"\b{re.escape(marker_norm)}\b")
            if marker_re.search(dst_canon) and not marker_re.search(src_canon):
                return True
        src_words = _tokens(source)
        dst_words = _tokens(translated)
        if len(src_words) <= 3 and len(dst_words) >= 9:
            return True
        return False

    def evaluate(
        self,
        source_text: str,
        translated_text: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        source = str(source_text or "")
        translated = str(translated_text or "")
        ctx = dict(context or {})

        glossary_hits, glossary_violations = self._glossary_check(source, translated)
        proper_noun_hits, proper_noun_preserved = self._proper_noun_check(source, translated)
        register_inconsistency, register_families = self._register_check(translated)
        semantic_drift = self._semantic_drift_check(source, translated)
        fragment_suspect = self._fragment_check(translated)
        semantic_hallucination_suspect = self._hallucination_check(source, translated)
        english_residue = self._english_residue_check(source, translated)

        src_len = max(1, len(_tokens(source)))
        dst_len = len(_tokens(translated))
        ratio = float(dst_len) / float(src_len)
        overtranslation_suspect = bool(ratio > 2.35 and src_len >= 2)
        undertranslation_suspect = bool(ratio < 0.45 and src_len >= 3)
        glossary_violation = bool(len(glossary_violations) > 0)
        proper_noun_corruption = bool(len(proper_noun_preserved) < len(proper_noun_hits))

        score = 100.0
        if glossary_violation:
            score -= 26.0
        if proper_noun_corruption:
            score -= 30.0
        if semantic_hallucination_suspect:
            score -= 26.0
        if semantic_drift:
            score -= 22.0
        if register_inconsistency:
            score -= 14.0
        if overtranslation_suspect:
            score -= 10.0
        if undertranslation_suspect:
            score -= 10.0
        if fragment_suspect:
            score -= 9.0
        if english_residue:
            score -= 40.0
        score = max(0.0, min(100.0, score))

        threshold = self._semantic_threshold_used()
        flags = {
            "semantic_hallucination_suspect": bool(semantic_hallucination_suspect),
            "glossary_violation": bool(glossary_violation),
            "proper_noun_corruption": bool(proper_noun_corruption),
            "register_inconsistency": bool(register_inconsistency),
            "semantic_drift": bool(semantic_drift),
            "overtranslation_suspect": bool(overtranslation_suspect),
            "undertranslation_suspect": bool(undertranslation_suspect),
            "fragment_suspect": bool(fragment_suspect),
        }

        absolute_block_reasons: List[str] = []
        for key in self.STRONG_FLAGS:
            if bool(flags.get(key, False)):
                absolute_block_reasons.append(key)
        if self.strict_mode:
            if overtranslation_suspect:
                absolute_block_reasons.append("overtranslation_suspect")
            if undertranslation_suspect:
                absolute_block_reasons.append("undertranslation_suspect")

        blocked = bool(score < threshold or len(absolute_block_reasons) > 0)
        return {
            **flags,
            "semantic_score": float(round(score, 2)),
            "semantic_threshold_used": float(threshold),
            "semantic_quality_gate_pass": bool(not blocked),
            "blocked": bool(blocked),
            "absolute_block_reasons": absolute_block_reasons,
            "glossary_hits": glossary_hits,
            "glossary_violations": glossary_violations,
            "proper_noun_hits": proper_noun_hits,
            "proper_noun_preserved": proper_noun_preserved,
            "register_policy": self.register_policy,
            "register_families_detected": register_families,
            "english_residue": bool(english_residue),
            "context_low_confidence": bool(ctx.get("context_low_confidence", False)),
            "segment_integrity_score": int(ctx.get("segment_integrity_score", 100) or 100),
        }
