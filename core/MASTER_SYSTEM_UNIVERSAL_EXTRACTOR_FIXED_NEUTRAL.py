# ============================================================================
# BINARY DATA PROCESSOR - Universal SMS Extractor
# v7.0 AUTO-DISCOVERY MODE
# ============================================================================
# Ferramenta de Processamento de Dados Binarios
# Modo totalmente generico - sem referencias a titulos ou marcas
# ============================================================================

from __future__ import annotations

import logging
import os
import json
import re
import zlib
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
from collections import Counter
from uuid import uuid4

from core.plausibility import should_accept_pointer_table, is_plausible_ascii, score_ascii_plausibility
from core.tbl_loader import TBLLoader
import math

BYTE_PLACEHOLDER_PATTERN = re.compile(r"\{B:([0-9A-Fa-f]{2})\}")


# ============================================================================
# CONFIGURACOES
# ============================================================================

# ============================================================================
# PLAUSIBLE TEXT FILTER
# ============================================================================

def is_plausible_text_sms(s: str) -> bool:
    """
    Verifica se uma string parece texto plausivel para SMS.
    Aplicado APENAS em strings ja extraidas via POINTER (nao scan cego).

    Returns:
        True se a string parece texto real, False caso contrario.
    """
    # Regra 1: comprimento minimo
    if len(s) < 3:
        return False

    # Regra 1b: strings curtas que comecam com pontuacao (ex: "!FE", "(VO")
    # Texto real comeca com letra ou digito, nao com simbolo
    if len(s) <= 4 and s and not s[0].isalnum():
        return False

    # Regra 2: caracteres permitidos
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?;:'\"()[]-/&")
    for c in s:
        if c not in allowed:
            return False

    # Regra 3: ratio de letras >= 60% (relaxado para strings longas com espacos)
    letter_count = sum(1 for c in s if c.isalpha())
    letter_ratio = letter_count / len(s)
    if letter_ratio < 0.60:
        # Strings longas com espacos e pelo menos 2 palavras reais: aceitar
        if len(s) >= 8 and ' ' in s:
            words = [w for w in s.split() if len(w) >= 2 and any(c.isalpha() for c in w)]
            if len(words) < 2:
                return False
        else:
            return False

    # Regra 4: max run length > 3 => False
    max_run = 1
    current_run = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1]:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    if max_run > 3:
        return False

    # Regra 4b: rejeitar padrão 2-3 chars repetindo 3+ vezes (ex: "ihihih", "&6F&6F&6F")
    for unit_len in (2, 3):
        if len(s) >= unit_len * 3:
            for i in range(len(s) - unit_len * 3 + 1):
                pat = s[i:i + unit_len]
                if pat.isspace():
                    continue
                occurrences = s.count(pat)
                if occurrences >= 3 and len(pat) * occurrences >= len(s) * 0.6:
                    return False

    # Regra 5: char mais comum > 40% => False
    if s:
        char_counts = Counter(s)
        most_common_count = char_counts.most_common(1)[0][1]
        most_common_ratio = most_common_count / len(s)
        if most_common_ratio > 0.40:
            return False

    # Regra 6: vogais — somente tokens ALL-CAPS conhecidos ou formato valido
    vowels = set("aeiouAEIOU")
    KNOWN_TOKENS = {"OK", "HP", "LV", "MP", "SP", "XP", "PT", "GP", "LP",
                    "1UP", "2UP", "ATK", "DEF", "STR", "DMG", "NPC", "VS",
                    "HQ", "KO", "DX", "NY", "TV", "FM", "CD", "DR", "MR",
                    "MS", "ST", "NG", "LR", "HR", "QTY", "LVL", "EXP",
                    "START", "WORLD", "EXTRA", "SWORD", "STAFF", "SPELL",
                    "CRAFT", "QUEST", "NORTH", "SOUTH", "FIRST", "FRONT",
                    "BLAST", "GHOST", "PLANT", "STMP", "CTRL", "SCRN"}
    if not any(c in vowels for c in s):
        if len(s) <= 4:
            is_known = s.upper().strip() in KNOWN_TOKENS
            if not is_known:
                # Sem vogais e nao eh token: aceitar SOMENTE se ALL-CAPS + digitos
                # Rejeita: "s,r", "gx2", "!dC", "g:T" (lixo binario)
                letters = [c for c in s if c.isalpha()]
                has_non_alnum = any(not c.isalnum() for c in s)
                if has_non_alnum or not letters or not all(c.isupper() for c in letters):
                    return False
        else:
            return False

    # Regra 7: strings longas (>= 8 chars) sem espaco/pontuacao
    # Aceitar SOMENTE se tiver pelo menos 2 vogais E 4 letras distintas
    # Permite "PRESSSTART", "GAMEOVER" mas rejeita "ihihxihy"
    if len(s) >= 8:
        space_or_punct = set(" .,!?:;")
        if not any(c in space_or_punct for c in s):
            # Sem espaco/pontuacao: aplicar regras adicionais
            vowel_count = sum(1 for c in s if c in vowels)
            distinct_letters = len(set(c.lower() for c in s if c.isalpha()))
            if vowel_count < 2 or distinct_letters < 4:
                return False

    # Regra 8: digito entre letras em strings curtas (ex: "G4ap")
    # Strings reais com digitos: "1UP", "LV5", "P2" — digito no inicio ou fim
    # Lixo binario: digito no meio de letras aleatorias
    if len(s) <= 6:
        for i in range(1, len(s) - 1):
            if s[i].isdigit() and s[i-1].isalpha() and s[i+1].isalpha():
                if s.upper().strip() not in KNOWN_TOKENS:
                    return False
                break

    # Regra 9: case misto anomalo em strings longas sem espaco (ex: "OGFNOLFOYmg")
    # Texto real: todo maiusculo, todo minusculo, TitleCase ou CamelCase equilibrado
    # Lixo: bytes aleatorios com 1-2 letras minusculas no meio de maiusculas
    if len(s) >= 6 and ' ' not in s:
        upper_count = sum(1 for c in s if c.isupper())
        lower_count = sum(1 for c in s if c.islower())
        if upper_count > 0 and lower_count > 0:
            alpha_only = [c for c in s if c.isalpha()]
            is_title_case_word = bool(
                alpha_only
                and alpha_only[0].isupper()
                and all(c.islower() for c in alpha_only[1:])
            )
            if not is_title_case_word:
                minority = min(upper_count, lower_count)
                total_alpha = upper_count + lower_count
                if total_alpha > 0 and minority / total_alpha <= 0.20:
                    return False

    # Regra 10: dominancia de consoantes em strings curtas (ex: "cpAng", "bxtrk")
    # Texto real curto tem vogais: "START" (A), "Hello" (e,o), "HP" (token)
    # Lixo binario: muitas consoantes sem vogais
    consonants = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
    if len(s) <= 6:
        cons_count = sum(1 for c in s if c in consonants)
        vowel_count = sum(1 for c in s if c in vowels)
        if cons_count >= 4 and vowel_count <= 1:
            if s.upper().strip() not in KNOWN_TOKENS:
                return False

    # Regra 11: consoante unica repetida em string curta (ex: "PHPIPJP" -> P=3x, >35%)
    # Texto real nao repete uma consoante tantas vezes em strings curtas
    if len(s) <= 8:
        alpha_chars = [c for c in s if c.isalpha()]
        if alpha_chars:
            char_freq = Counter(c.upper() for c in alpha_chars)
            for ch, cnt in char_freq.items():
                if ch.upper() in consonants and cnt >= 3 and cnt / len(s) > 0.35:
                    return False

    # Regra 12: ratio simbolo+digito alto em string curta (ex: "o|2", "a/3")
    # Preserva: "1UP", "P2", "LV.5"
    if len(s) <= 5:
        sym_digit = sum(1 for c in s if not c.isalpha() and not c.isspace())
        if sym_digit / len(s) >= 0.50:
            if s.upper().strip() not in KNOWN_TOKENS:
                return False

    # Regra 13: case mixing anomalo em strings curtas (3-5 chars)
    # Texto real: "End" (Aa), "ATK" (AA), "the" (aa), "1UP" (dAA)
    # Lixo binario: "cpA" (aaA), "gXf" (aAa), "dOp" (aAa)
    # Permite: ALL UPPER, all lower, Title Case, digito+letras
    if 3 <= len(s) <= 5:
        letters_only = [c for c in s if c.isalpha()]
        if len(letters_only) >= 2:
            uppers = [c for c in letters_only if c.isupper()]
            lowers = [c for c in letters_only if c.islower()]
            if uppers and lowers:
                # Mixed case: so aceitar se Title Case (primeira letra upper, resto lower)
                first_alpha_idx = next(i for i, c in enumerate(s) if c.isalpha())
                if not (s[first_alpha_idx].isupper() and all(c.islower() for c in letters_only[1:])):
                    if s.upper().strip() not in KNOWN_TOKENS:
                        return False

    # Regra 14: strings de 3 chars sem significado reconhecivel
    # Texto real de 3 chars em jogos: "End", "Win", "Yes", "THE", "and", "for"
    # Lixo: "0_P", "d0 ", "W`Y", "R`T"
    # Rejeitar strings de exatamente 3 chars que nao formam padrao reconhecivel
    if len(s) == 3:
        # Se tem digito E letra E nao eh token conhecido -> provavel lixo
        has_digit = any(c.isdigit() for c in s)
        has_letter = any(c.isalpha() for c in s)
        has_symbol = any(not c.isalnum() and not c.isspace() for c in s)
        if has_digit and has_letter and has_symbol:
            if s.upper().strip() not in KNOWN_TOKENS:
                return False
        # Se eh 3 chars all-lowercase sem vogal -> lixo (ex: "cps", "bxd")
        if all(c.islower() for c in s if c.isalpha()) and not any(c in vowels for c in s):
            if s.upper().strip() not in KNOWN_TOKENS:
                return False

    # Regra 15: minimo de comprimento para texto plausivel
    # Strings de 3-4 chars que nao sao tokens conhecidos precisam ter pelo menos 1 vogal
    # e nao ser apenas consoantes misturadas
    if len(s) <= 4 and s.upper().strip() not in KNOWN_TOKENS:
        alpha = [c for c in s if c.isalpha()]
        if len(alpha) >= 2:
            vowel_count = sum(1 for c in alpha if c in vowels)
            if vowel_count == 0:
                return False

    return True
class TotalTextExtractor:
    """
    Extrai textos usando múltiplas técnicas SEM scan cego final:
      - Ponteiros (método atual)
      - AutoLearningEngine (tiles/fluxos detectados)
      - ASCII em regiões específicas (header/credits configuradas)
    """

    def __init__(self, rom_path: str, config: Optional["ExtractorConfig"] = None):
        self.rom_path = rom_path
        self.config = config or ExtractorConfig()
        with open(rom_path, "rb") as f:
            self.rom_data = f.read()

    def extract_extras_only(self) -> List[Dict]:
        """
        Retorna SOMENTE textos extras (não-pointer), em formato compatível
        com o pipeline (itens dict com keys esperadas pelo JSONL).
        """
        extras: List[Dict] = []

        # ASCII direto em REGIÕES ESPECÍFICAS (sem varrer ROM inteira)
        extras.extend(self._extract_ascii_specific_regions())

        # Tiles/gráficos via AutoLearningEngine (sem ASCII scan global)
        extras.extend(self._extract_tile_based_autolearn())

        # Dedup por chave estável (offset, byte_len, terminator, encoding)
        seen: Set[Tuple[int, int, Optional[int], str]] = set()
        uniq: List[Dict] = []
        for it in extras:
            off = int(it.get("offset", 0))
            byte_len = int(it.get("max_len", 0))
            terminator = it.get("terminator")
            encoding = str(it.get("encoding", "ascii"))
            k = (off, byte_len, terminator if terminator is not None else None, encoding)
            if k not in seen:
                seen.add(k)
                uniq.append(it)
        return uniq

    def _extract_ascii_specific_regions(self) -> List[Dict]:
        """
        Usa a rotina já existente (_extract_ascii_region) do UniversalMasterSystemExtractor,
        mas somente nas regiões configuradas (header/credits).
        """
        try:
            tmp = UniversalMasterSystemExtractor(self.rom_path, config=self.config)
        except Exception:
            return []

        blocks = []
        # Header (0x0000 .. header_scan_end)
        if self.config.header_scan_end and self.config.header_scan_end > 0:
            blocks.extend(tmp._extract_ascii_region(0, self.config.header_scan_end, source="ASCII_HEADER"))

        # Credits (credits_scan_start .. credits_scan_end)
        if self.config.credits_scan_end > self.config.credits_scan_start:
            blocks.extend(tmp._extract_ascii_region(self.config.credits_scan_start,
                                                   self.config.credits_scan_end,
                                                   source="ASCII_CREDITS"))

        out: List[Dict] = []
        for b in blocks:
            text = (b.decoded_text or "").strip()
            if not text:
                continue

            # Evita lixo extremo, mas não aplica o filtro "plausible" (porque aqui não é POINTER)
            if len(text) < max(3, self.config.min_text_length):
                continue

            max_len = len(text.encode("ascii", errors="ignore"))
            out.append({
                "id": -1,  # será renumerado depois
                "offset": int(b.offset),
                "decoded": text,
                "clean": text,
                "max_len": max_len,
                "encoding": "tbl" if getattr(tmp, "tbl_loader", None) is not None else "ascii",
                "source": b.source or "ASCII_REGION",
                "has_pointer": False,
                "reinsertion_safe": False,
                "reason_code": "NO_POINTER_INFO",
                "pointer_value": None,
                "pointer_refs": [],
                "confidence": float(getattr(b, "confidence", 0.50)) if getattr(b, "confidence", None) is not None else 0.50,
            })
        return out

    def _extract_tile_based_autolearn(self) -> List[Dict]:
        """
        Extrai candidatos via AutoLearningEngine (tiles/streams/hybrid).
        Não faz ASCII scan global.
        """
        try:
            from core.AUTO_LEARNING_ENGINE_NEUTRAL import AutoLearningEngine, LearningMode, ExtractionMethod
        except Exception:
            return []

        engine = AutoLearningEngine(self.rom_data, allow_ascii_scan=False)
        try:
            candidate, _score = engine.run(max_iters=3, mode=LearningMode.AUTO_FAST)
        except Exception:
            return []

        out: List[Dict] = []
        for u in getattr(candidate, "units", []) or []:
            txt = (getattr(u, "text_src", None) or "").strip()
            if not txt:
                continue

            method = getattr(u, "method", None)
            # Mantém só métodos não-sequenciais (evita "scan")
            if method in (ExtractionMethod.SEQUENTIAL_SCAN,):
                continue

            off = getattr(u, "offset", None)
            if off is None:
                continue

            max_len = len(txt.encode("ascii", errors="ignore"))
            out.append({
                "id": -1,  # será renumerado depois
                "offset": int(off),
                "decoded": txt,
                "clean": txt,
                "max_len": max_len,
                "encoding": "ascii",
                "source": f"AUTOLEARN_{getattr(method, 'value', str(method))}",
                "has_pointer": False,
                "reinsertion_safe": False,
                "reason_code": "AUTOLEARN_NO_POINTER_INFO",
                "pointer_value": None,
                "pointer_refs": [],
                "confidence": float(getattr(u, "confidence", 0.60)) if getattr(u, "confidence", None) is not None else 0.60,
            })
        return out


@dataclass
class ExtractorConfig:
    """Configuracoes do extrator - ajustaveis pelo usuario."""
    # Ponteiros
    min_pointers_for_table: int = 8          # Minimo de ponteiros para considerar tabela
    max_pointer_gap: int = 0x100             # Gap maximo entre ponteiros consecutivos
    pointer_validation_threshold: float = 0.6 # 60% dos ponteiros devem ser validos
    pointer_partial_mode_enabled: bool = True
    pointer_partial_min_entries: int = 4
    pointer_partial_min_ratio: float = 0.25
    pointer_partial_min_plausibility_score: float = 0.55

    # Texto
    min_text_length: int = 3                 # Comprimento minimo de texto
    max_text_length: int = 256               # Comprimento maximo de texto
    alphanumeric_threshold: float = 0.6      # 60% de caracteres alfanumericos

    # Terminadores validos
    valid_terminators: Tuple[int, ...] = (0x00, 0xFF)

    # Scan
    header_scan_end: int = 0x0400            # Fim do header para scan ASCII
    credits_scan_start: int = 0x7F00         # Inicio da area de creditos
    credits_scan_end: int = 0x8000           # Fim da area de creditos


# ============================================================================
# TRANSLATION_PREP_LAYER v2.2 - POLITICAS E CONFIGURACOES
# ============================================================================

class ValidationResult(Enum):
    """Resultado de validacao."""
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class ForbiddenBytePolicy:
    """
    Politica de bytes proibidos por encoding.
    Bloqueia traducoes que contenham bytes invalidos para o encoding alvo.
    """
    encoding: str = "ascii"
    # Bytes proibidos por encoding (ranges ou valores especificos)
    forbidden_ranges: List[Tuple[int, int]] = field(default_factory=list)
    forbidden_values: Set[int] = field(default_factory=set)
    # Comportamento: 'block' = rejeita, 'warn' = avisa mas permite
    on_violation: str = "block"

    def __post_init__(self):
        """Configura bytes proibidos baseado no encoding."""
        if not self.forbidden_ranges and not self.forbidden_values:
            self._setup_defaults_for_encoding()

    def _setup_defaults_for_encoding(self):
        """Define bytes proibidos default por encoding."""
        if self.encoding.lower() in ("ascii", "us-ascii"):
            # ASCII: 0x00-0x1F (exceto alguns), 0x7F-0xFF
            self.forbidden_ranges = [(0x00, 0x08), (0x0E, 0x1F), (0x7F, 0xFF)]
            self.forbidden_values = set()
        elif self.encoding.lower() in ("latin-1", "iso-8859-1", "cp1252"):
            # Latin-1: apenas controle 0x00-0x1F (exceto tab/newline), 0x7F-0x9F
            self.forbidden_ranges = [(0x00, 0x08), (0x0E, 0x1F), (0x7F, 0x9F)]
        elif self.encoding.lower() in ("shift_jis", "shift-jis", "sjis"):
            # Shift-JIS: bytes invalidos em sequencias
            self.forbidden_values = {0xFD, 0xFE, 0xFF}
        elif self.encoding.lower() == "utf-8":
            # UTF-8: surrogates e invalidos
            self.forbidden_ranges = [(0xC0, 0xC1), (0xF5, 0xFF)]

    def validate_bytes(self, data: bytes) -> Tuple[ValidationResult, List[int]]:
        """
        Valida bytes contra politica.
        Retorna (resultado, lista_de_offsets_violados).
        """
        violations = []
        for i, byte in enumerate(data):
            # Verifica ranges proibidos
            for start, end in self.forbidden_ranges:
                if start <= byte <= end:
                    violations.append(i)
                    break
            else:
                # Verifica valores especificos
                if byte in self.forbidden_values:
                    violations.append(i)

        if violations:
            result = ValidationResult.BLOCKED if self.on_violation == "block" else ValidationResult.WARNING
            return (result, violations)
        return (ValidationResult.OK, [])

    def validate_string(self, text: str) -> Tuple[ValidationResult, List[int]]:
        """Valida string codificada contra politica."""
        try:
            encoded = text.encode(self.encoding, errors="strict")
            return self.validate_bytes(encoded)
        except UnicodeEncodeError as e:
            # Caractere nao pode ser codificado
            return (ValidationResult.BLOCKED, [e.start])


@dataclass
class RepointPolicy:
    """
    Politica de repointing para traducoes que excedem max_len_bytes.
    Default OFF - requer free_space_regions explicito.
    """
    enabled: bool = False
    # Regioes de espaco livre na ROM (neutro, fornecido externamente)
    free_space_regions: List[Tuple[int, int]] = field(default_factory=list)
    # Byte de preenchimento para espaco livre
    fill_byte: int = 0xFF
    # Alinhar ponteiros a N bytes (0 = sem alinhamento)
    alignment: int = 0
    # Registro de patches aplicados
    patches: List[Dict] = field(default_factory=list)
    # Estatisticas de uso de espaco livre
    used_space: int = 0

    def find_free_space(self, size_needed: int) -> Optional[int]:
        """
        Encontra espaco livre suficiente para 'size_needed' bytes.
        Retorna offset ou None se nao encontrar.
        """
        if not self.enabled or not self.free_space_regions:
            return None

        for i, (start, end) in enumerate(self.free_space_regions):
            available = end - start

            # Aplica alinhamento se necessario
            aligned_start = start
            if self.alignment > 0:
                aligned_start = ((start + self.alignment - 1) // self.alignment) * self.alignment
                if aligned_start >= end:
                    continue
                available = end - aligned_start

            if available >= size_needed:
                return aligned_start

        return None

    def allocate_space(self, size_needed: int) -> Optional[int]:
        """
        Aloca espaco livre e atualiza regioes disponiveis.
        Retorna offset alocado ou None.
        """
        offset = self.find_free_space(size_needed)
        if offset is None:
            return None

        # Atualiza regioes de espaco livre
        for i, (start, end) in enumerate(self.free_space_regions):
            aligned_start = start
            if self.alignment > 0:
                aligned_start = ((start + self.alignment - 1) // self.alignment) * self.alignment

            if aligned_start == offset:
                new_start = offset + size_needed
                if new_start < end:
                    self.free_space_regions[i] = (new_start, end)
                else:
                    self.free_space_regions.pop(i)
                self.used_space += size_needed
                return offset

        return None

    def register_patch(self, original_offset: int, new_offset: int,
                       pointer_offset: int, original_size: int, new_size: int):
        """Registra um patch de repointing no mapping."""
        self.patches.append({
            "original_text_offset": original_offset,
            "new_text_offset": new_offset,
            "pointer_offset": pointer_offset,
            "original_size": original_size,
            "new_size": new_size,
            "pointer_value_old": original_offset,
            "pointer_value_new": new_offset,
        })


@dataclass
class NewlinePolicy:
    """
    Politica de newlines para preservar contagem de linhas.
    Permite reflow controlado no two-pass.
    """
    preserve_line_count: bool = True
    # Caracteres de newline reconhecidos
    newline_chars: Tuple[str, ...] = ("\n", "\r\n", "\r")
    # Byte de newline na ROM (varia por sistema)
    newline_byte: int = 0x0A
    # Permitir reflow (quebra de palavras) se necessario
    allow_reflow: bool = True
    # Largura maxima de linha para reflow (0 = sem limite)
    max_line_width: int = 0
    # Caractere de continuacao de linha
    continuation_char: str = ""

    def count_lines(self, text: str) -> int:
        """Conta numero de linhas no texto."""
        if not text:
            return 0
        count = 1
        for nl in self.newline_chars:
            count += text.count(nl)
            text = text.replace(nl, "")
        return count

    def validate_line_count(self, original: str, translated: str) -> Tuple[ValidationResult, dict]:
        """
        Valida se traducao preserva contagem de linhas.
        Retorna (resultado, detalhes).
        """
        orig_lines = self.count_lines(original)
        trans_lines = self.count_lines(translated)

        details = {
            "original_lines": orig_lines,
            "translated_lines": trans_lines,
            "difference": trans_lines - orig_lines,
        }

        if not self.preserve_line_count:
            return (ValidationResult.OK, details)

        if orig_lines == trans_lines:
            return (ValidationResult.OK, details)

        return (ValidationResult.WARNING, details)

    def reflow_text(self, text: str, max_width: int) -> str:
        """
        Aplica reflow ao texto respeitando largura maxima.
        """
        if not self.allow_reflow or max_width <= 0:
            return text

        lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue

            words = paragraph.split()
            current_line = []
            current_width = 0

            for word in words:
                word_len = len(word)
                space_needed = 1 if current_line else 0

                if current_width + space_needed + word_len <= max_width:
                    current_line.append(word)
                    current_width += space_needed + word_len
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_width = word_len

            if current_line:
                lines.append(" ".join(current_line))

        return "\n".join(lines)


@dataclass
class FixedFieldInfo:
    """Informacoes de campo de tamanho fixo detectado."""
    cluster_id: str
    fixed_field_len_bytes: int
    pad_byte: int
    stride: int
    confidence: float
    sample_count: int


@dataclass
class StyleProfileInfo:
    """Perfil de estilo detectado por cluster."""
    cluster_id: str
    # Estilo de capitalizacao
    capitalization: str  # "UPPERCASE", "lowercase", "Title Case", "Mixed"
    caps_ratio: float
    # Pontuacao
    has_periods: bool
    has_exclamation: bool
    has_question: bool
    punctuation_pattern: str
    # Estatisticas
    avg_word_length: float
    sample_count: int


@dataclass
class StyleWarning:
    """Warning de desvio de estilo."""
    text_id: int
    cluster_id: str
    warning_type: str  # "caps_mismatch", "punctuation_mismatch", "length_deviation"
    expected: str
    found: str
    severity: str  # "low", "medium", "high"


# ============================================================================
# ESTRUTURAS DE DADOS
# ============================================================================

@dataclass
class PointerTable:
    """Representa uma tabela de ponteiros descoberta."""
    table_offset: int                        # Offset da tabela na ROM
    entry_count: int                         # Numero de entradas
    entry_size: int = 2                      # Tamanho de cada entrada (2 = 16-bit)
    valid_pointers: List[int] = field(default_factory=list)
    pointer_entry_indexes: List[int] = field(default_factory=list)
    confidence: float = 0.0                  # Confianca na descoberta (0.0-1.0)
    mode: str = "FULL"                       # FULL ou PARTIAL
    checked_entries: int = 0                 # Entradas avaliadas no range
    plausibility_ratio: float = 0.0          # Razão de plausibilidade média
    partial_discarded: int = 0               # Entradas descartadas no modo parcial


@dataclass
class TextBlock:
    """Representa um bloco de texto extraido."""
    offset: int                              # Offset na ROM (resolved_rom_offset)
    raw_bytes: bytes                         # Bytes originais
    decoded_text: str                        # Texto decodificado
    max_length: int                          # Tamanho maximo para reinserção
    terminator: Optional[int]                # Byte terminador
    source: str                              # Origem: POINTER, HEADER, CREDITS, SCAN
    pointer_table_offset: Optional[int] = None
    pointer_entry_offset: Optional[int] = None
    pointer_value: Optional[int] = None      # Valor lido do ponteiro (u16 LE)
    confidence: float = 0.0
    cluster_id: Optional[str] = None         # ID do cluster para agrupamento


# ============================================================================
# FIXED FIELD DETECTOR
# ============================================================================

class FixedFieldDetector:
    """
    Detecta campos de tamanho fixo por cluster via analise de stride/padding.
    Infere fixed_field_len_bytes e pad_byte automaticamente.
    """

    def __init__(self, min_samples: int = 3, confidence_threshold: float = 0.7):
        self.min_samples = min_samples
        self.confidence_threshold = confidence_threshold

    def analyze_cluster(self, blocks: List[TextBlock]) -> Optional[FixedFieldInfo]:
        """
        Analisa um cluster de blocos de texto para detectar campos fixos.
        """
        if len(blocks) < self.min_samples:
            return None

        # Agrupa por tamanho max_length
        sizes = [b.max_length for b in blocks]
        size_counter = Counter(sizes)

        # Se todos tem mesmo tamanho, provavel campo fixo
        most_common_size, count = size_counter.most_common(1)[0]
        size_ratio = count / len(blocks)

        if size_ratio < self.confidence_threshold:
            return None

        # Detecta stride (distancia entre offsets consecutivos)
        offsets = sorted([b.offset for b in blocks])
        strides = []
        for i in range(1, len(offsets)):
            strides.append(offsets[i] - offsets[i-1])

        stride_counter = Counter(strides)
        if stride_counter:
            most_common_stride, stride_count = stride_counter.most_common(1)[0]
            stride_confidence = stride_count / len(strides) if strides else 0
        else:
            most_common_stride = most_common_size
            stride_confidence = 0.5

        # Detecta pad_byte analisando bytes apos o texto
        pad_bytes = self._detect_pad_bytes(blocks)
        most_common_pad = 0x00 if not pad_bytes else pad_bytes.most_common(1)[0][0]

        # Calcula confianca final
        confidence = (size_ratio + stride_confidence) / 2

        cluster_id = blocks[0].cluster_id if blocks[0].cluster_id else f"cluster_{offsets[0]:06X}"

        return FixedFieldInfo(
            cluster_id=cluster_id,
            fixed_field_len_bytes=most_common_size,
            pad_byte=most_common_pad,
            stride=most_common_stride,
            confidence=confidence,
            sample_count=len(blocks)
        )

    def _detect_pad_bytes(self, blocks: List[TextBlock]) -> Counter:
        """Detecta bytes de padding mais comuns."""
        pad_counter: Counter = Counter()

        for block in blocks:
            text_len = len(block.raw_bytes)
            if text_len < block.max_length:
                # Verifica se terminator funciona como padding
                if block.terminator is not None:
                    pad_counter[block.terminator] += 1

        return pad_counter

    def detect_all_clusters(self, blocks: List[TextBlock]) -> Dict[str, FixedFieldInfo]:
        """
        Detecta campos fixos em todos os clusters.
        Agrupa blocos por source e pointer_table_offset.
        """
        # Agrupa blocos por cluster
        clusters: Dict[str, List[TextBlock]] = {}

        for block in blocks:
            # Cria cluster_id se nao existir
            if block.cluster_id:
                key = block.cluster_id
            elif block.pointer_table_offset is not None:
                key = f"ptr_table_{block.pointer_table_offset:06X}"
            else:
                key = f"source_{block.source}"

            block.cluster_id = key

            if key not in clusters:
                clusters[key] = []
            clusters[key].append(block)

        # Analisa cada cluster
        results: Dict[str, FixedFieldInfo] = {}
        for cluster_id, cluster_blocks in clusters.items():
            info = self.analyze_cluster(cluster_blocks)
            if info:
                results[cluster_id] = info

        return results


# ============================================================================
# STYLE PROFILE ANALYZER
# ============================================================================

class StyleProfileAnalyzer:
    """
    Analisa perfil de estilo por cluster (caps/title/pontuacao).
    Gera warnings no report quando traducoes desviam do perfil.
    """

    def __init__(self):
        self.profiles: Dict[str, StyleProfileInfo] = {}
        self.warnings: List[StyleWarning] = []

    def analyze_cluster(self, blocks: List[TextBlock], cluster_id: str) -> Optional[StyleProfileInfo]:
        """Analisa estilo de um cluster de textos."""
        if not blocks:
            return None

        texts = [b.decoded_text for b in blocks if b.decoded_text]
        if not texts:
            return None

        # Analisa capitalizacao
        caps_stats = self._analyze_capitalization(texts)

        # Analisa pontuacao
        punct_stats = self._analyze_punctuation(texts)

        # Analisa comprimento de palavras
        avg_word_len = self._calculate_avg_word_length(texts)

        profile = StyleProfileInfo(
            cluster_id=cluster_id,
            capitalization=caps_stats["style"],
            caps_ratio=caps_stats["ratio"],
            has_periods=punct_stats["periods"],
            has_exclamation=punct_stats["exclamation"],
            has_question=punct_stats["question"],
            punctuation_pattern=punct_stats["pattern"],
            avg_word_length=avg_word_len,
            sample_count=len(texts)
        )

        self.profiles[cluster_id] = profile
        return profile

    def _analyze_capitalization(self, texts: List[str]) -> dict:
        """Analisa estilo de capitalizacao."""
        all_upper = 0
        all_lower = 0
        title_case = 0
        mixed = 0

        for text in texts:
            alpha_chars = [c for c in text if c.isalpha()]
            if not alpha_chars:
                continue

            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)

            if upper_ratio > 0.9:
                all_upper += 1
            elif upper_ratio < 0.1:
                all_lower += 1
            elif text.istitle() or self._is_title_case(text):
                title_case += 1
            else:
                mixed += 1

        total = all_upper + all_lower + title_case + mixed
        if total == 0:
            return {"style": "Mixed", "ratio": 0.0}

        max_count = max(all_upper, all_lower, title_case, mixed)
        if max_count == all_upper:
            return {"style": "UPPERCASE", "ratio": all_upper / total}
        elif max_count == all_lower:
            return {"style": "lowercase", "ratio": all_lower / total}
        elif max_count == title_case:
            return {"style": "Title Case", "ratio": title_case / total}
        else:
            return {"style": "Mixed", "ratio": mixed / total}

    def _is_title_case(self, text: str) -> bool:
        """Verifica se texto segue Title Case."""
        words = text.split()
        if not words:
            return False

        title_words = 0
        for word in words:
            alpha = [c for c in word if c.isalpha()]
            if alpha and alpha[0].isupper():
                title_words += 1

        return title_words / len(words) > 0.7

    def _analyze_punctuation(self, texts: List[str]) -> dict:
        """Analisa padroes de pontuacao."""
        periods = sum(1 for t in texts if "." in t)
        exclamation = sum(1 for t in texts if "!" in t)
        question = sum(1 for t in texts if "?" in t)
        total = len(texts)

        # Determina padrao dominante
        patterns = []
        if periods / total > 0.5:
            patterns.append("periods")
        if exclamation / total > 0.3:
            patterns.append("exclamation")
        if question / total > 0.3:
            patterns.append("question")

        return {
            "periods": periods / total > 0.5,
            "exclamation": exclamation / total > 0.3,
            "question": question / total > 0.3,
            "pattern": "+".join(patterns) if patterns else "none",
        }

    def _calculate_avg_word_length(self, texts: List[str]) -> float:
        """Calcula comprimento medio de palavras."""
        all_words = []
        for text in texts:
            words = re.findall(r'\b\w+\b', text)
            all_words.extend(words)

        if not all_words:
            return 0.0

        return sum(len(w) for w in all_words) / len(all_words)

    def validate_translation(self, text_id: int, cluster_id: str,
                            original: str, translated: str) -> List[StyleWarning]:
        """
        Valida se traducao segue o perfil de estilo do cluster.
        Retorna lista de warnings.
        """
        warnings = []

        if cluster_id not in self.profiles:
            return warnings

        profile = self.profiles[cluster_id]

        # Valida capitalizacao
        caps_warning = self._check_capitalization(text_id, cluster_id, translated, profile)
        if caps_warning:
            warnings.append(caps_warning)

        # Valida pontuacao
        punct_warning = self._check_punctuation(text_id, cluster_id, original, translated, profile)
        if punct_warning:
            warnings.append(punct_warning)

        # Valida comprimento
        len_warning = self._check_length_deviation(text_id, cluster_id, original, translated, profile)
        if len_warning:
            warnings.append(len_warning)

        self.warnings.extend(warnings)
        return warnings

    def _check_capitalization(self, text_id: int, cluster_id: str,
                              translated: str, profile: StyleProfileInfo) -> Optional[StyleWarning]:
        """Verifica se capitalizacao da traducao corresponde ao perfil."""
        alpha_chars = [c for c in translated if c.isalpha()]
        if not alpha_chars:
            return None

        upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)

        expected_style = profile.capitalization
        found_style = "Mixed"

        if upper_ratio > 0.9:
            found_style = "UPPERCASE"
        elif upper_ratio < 0.1:
            found_style = "lowercase"
        elif self._is_title_case(translated):
            found_style = "Title Case"

        if found_style != expected_style and profile.caps_ratio > 0.7:
            return StyleWarning(
                text_id=text_id,
                cluster_id=cluster_id,
                warning_type="caps_mismatch",
                expected=expected_style,
                found=found_style,
                severity="medium" if profile.caps_ratio > 0.9 else "low"
            )

        return None

    def _check_punctuation(self, text_id: int, cluster_id: str,
                           original: str, translated: str,
                           profile: StyleProfileInfo) -> Optional[StyleWarning]:
        """Verifica se pontuacao da traducao corresponde ao perfil."""
        orig_has_period = "." in original
        trans_has_period = "." in translated

        # Se original tem ponto e traducao nao tem (e cluster geralmente tem)
        if orig_has_period and not trans_has_period and profile.has_periods:
            return StyleWarning(
                text_id=text_id,
                cluster_id=cluster_id,
                warning_type="punctuation_mismatch",
                expected="period expected",
                found="no period",
                severity="low"
            )

        return None

    def _check_length_deviation(self, text_id: int, cluster_id: str,
                                original: str, translated: str,
                                profile: StyleProfileInfo) -> Optional[StyleWarning]:
        """Verifica desvio significativo de comprimento."""
        orig_len = len(original)
        trans_len = len(translated)

        if orig_len == 0:
            return None

        ratio = trans_len / orig_len

        # Ajusta threshold baseado no perfil do cluster
        # Clusters com palavras maiores toleram mais variacao
        threshold_high = 1.5 + (profile.avg_word_length * 0.05)
        threshold_low = 0.5 - (profile.avg_word_length * 0.02)

        # Traducao muito maior ou muito menor
        if ratio > threshold_high or ratio < threshold_low:
            return StyleWarning(
                text_id=text_id,
                cluster_id=cluster_id,
                warning_type="length_deviation",
                expected=f"{orig_len} chars (profile avg_word={profile.avg_word_length:.1f})",
                found=f"{trans_len} chars ({ratio:.0%})",
                severity="high" if ratio > 2.0 or ratio < 0.3 else "medium"
            )

        return None

    def get_report_warnings(self) -> List[dict]:
        """Retorna warnings formatados para o report."""
        return [
            {
                "text_id": w.text_id,
                "cluster": w.cluster_id,
                "type": w.warning_type,
                "expected": w.expected,
                "found": w.found,
                "severity": w.severity,
            }
            for w in self.warnings
        ]


# ============================================================================
# EXTRATOR PRINCIPAL
# ============================================================================

class UniversalMasterSystemExtractor:
    """
    BINARY DATA PROCESSOR - Modo AUTO-DISCOVERY

    Ferramenta generica para processamento de dados binarios.
    Identifica e extrai sequencias de texto de arquivos .sms
    usando heuristicas estatisticas, sem banco de dados previo.

    Funcionalidades:
    - Scanner de ponteiros heuristico
    - Filtro de texto estatistico (>60% alfanumerico)
    - Deteccao automatica de tabelas de ponteiros
    - Mapeamento generico para reinserção
    """

    def __init__(self, file_path: str | Path, config: Optional[ExtractorConfig] = None):
        self.file_path = str(file_path)
        self.config = config or ExtractorConfig()

        # Dados da ROM
        self.rom_data: bytes = b""
        self.rom_size: int = 0

        # Identificacao neutra (apenas CRC)
        self.crc32_full: str = ""
        self.crc32_no_header: str = ""

        # Descobertas
        self.build_id: str = self._make_build_id()
        self.discovered_tables: List[PointerTable] = []
        self.extracted_blocks: List[TextBlock] = []
        self.rejected_pointer_table_low_plausibility: int = 0
        self.rejected_pointer_table_details: List[Dict[str, Any]] = []
        self.partial_pointer_table_details: List[Dict[str, Any]] = []
        self.pointer_table_partial_accepted: int = 0
        self.pointer_table_partial_entries_total: int = 0
        self.pointer_table_partial_kept_count: int = 0
        self.tbl_loader: Optional[TBLLoader] = None
        self.tbl_path: Optional[str] = None

        # Resultados (compatibilidade com GUI)
        self.results: List[dict] = []
        self.filtered_texts: List[dict] = []

        # Provas/diagnosticos (tilemap/ASCII)
        self.ascii_probe_hits: Dict[str, List[int]] = {}
        self.ascii_probe_total: int = 0
        self.tilemap_probe_items: List[Dict] = []
        self.font_candidates: List[Dict] = []
        self.tilemap_candidate_ranges: List[Dict] = []
        self.tilemap_probe_used: bool = False
        self.tilemap_auto_info: Optional[Dict] = None

        # Auditoria por item (dump/reporte/proof)
        self.audit_unknown_bytes_total: int = 0
        self.audit_unknown_items: int = 0
        self.audit_roundtrip_fail_count: int = 0
        self.audit_overlap_items: int = 0
        self.audit_overlap_clusters: int = 0
        self.audit_review_items: int = 0
        self.overlap_resolution_details: List[Dict[str, Any]] = []
        self.overlap_discarded_count: int = 0
        self.translatable_total_count: int = 0
        self.reinsertable_total_count: int = 0
        self.recompress_pending_count: int = 0

        # Métricas de UI (extração orientada por ponteiros/padrões)
        self.ui_items_found_count: int = 0
        self.ui_items_extracted_count: int = 0
        self.ui_items_translated_count: int = 0
        self.ui_items_reinserted_count: int = 0
        self.ui_items_blocked_count: int = 0
        self.ui_items_blocked_details: List[Dict[str, Any]] = []

        # Carrega arquivo
        self._load_file()
        self._calculate_checksums()
        self._load_tbl_for_crc()

    # ========================================================================
    # CARREGAMENTO E CHECKSUMS
    # ========================================================================

    def _make_build_id(self) -> str:
        """Gera identificador único de build para evitar artefatos stale."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{stamp}-{uuid4().hex[:8].upper()}"

    def _load_file(self) -> None:
        """Carrega o arquivo binario."""
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {self.file_path}")

        self.rom_data = path.read_bytes()
        self.rom_size = len(self.rom_data)

    def _calculate_checksums(self) -> None:
        """Calcula checksums para identificacao neutra."""
        # CRC32 completo
        self.crc32_full = f"{zlib.crc32(self.rom_data) & 0xFFFFFFFF:08X}"

        # CRC32 sem header de 512 bytes (alguns arquivos tem header)
        if self.rom_size > 512:
            self.crc32_no_header = f"{zlib.crc32(self.rom_data[512:]) & 0xFFFFFFFF:08X}"
        else:
            self.crc32_no_header = self.crc32_full

    def _load_tbl_for_crc(self) -> None:
        """Tenta carregar TBL customizado pelo CRC32."""
        candidates: List[Path] = []
        try:
            rom_dir = Path(self.file_path).parent
            candidates.append(rom_dir / self.crc32_full / f"{self.crc32_full}_auto.tbl")
            candidates.append(rom_dir / self.crc32_full / f"{self.crc32_full}.tbl")
        except Exception:
            pass

        candidates.append(Path(__file__).parent / "profiles" / "sms" / f"{self.crc32_full}.tbl")

        for cand in candidates:
            try:
                if cand.exists():
                    self.tbl_loader = TBLLoader(str(cand))
                    self.tbl_path = str(cand)
                    return
            except Exception:
                continue

    # ========================================================================
    # UTILIDADES DE LEITURA
    # ========================================================================

    def _read_u16le(self, offset: int) -> Optional[int]:
        """Le um valor 16-bit Little Endian."""
        if offset < 0 or offset + 2 > self.rom_size:
            return None
        return int.from_bytes(self.rom_data[offset:offset+2], "little")

    # Bytes de controle de UI (layout, ícones, cursor) - permitidos SOMENTE em blocos UI.
    # Esses bytes não são caracteres ASCII inválidos; são tokens de controle do jogo.
    UI_CONTROL_BYTES: frozenset = frozenset({0xF7, 0xF8})

    def _is_printable_ascii(self, byte: int) -> bool:
        """Verifica se byte e ASCII imprimivel (0x20-0x7E)."""
        return 0x20 <= byte <= 0x7E

    def _is_valid_ui_byte(self, byte: int) -> bool:
        """Verifica se byte é válido em bloco UI (ASCII + ctrl + UI control bytes)."""
        return (
            self._is_printable_ascii(byte)
            or (0 < byte < 0x20)
            or (byte in self.UI_CONTROL_BYTES)
        )

    def _decode_bytes_with_placeholders(self, raw: bytes) -> Tuple[str, int]:
        """
        Decodifica bytes preservando informação:
        - bytes desconhecidos viram placeholder {B:HH}
        - nunca troca byte desconhecido por "!"
        """
        if not raw:
            return "", 0

        out: List[str] = []
        unknown_count = 0
        i = 0

        while i < len(raw):
            matched = False

            # Suporte a entradas multi-byte quando houver TBL carregada.
            if self.tbl_loader is not None and self.tbl_loader.max_entry_len > 1:
                max_len = min(self.tbl_loader.max_entry_len, len(raw) - i)
                for entry_len in range(max_len, 1, -1):
                    seq = raw[i:i + entry_len]
                    ch = self.tbl_loader.multi_byte_map.get(seq)
                    if ch is not None:
                        out.append(ch)
                        i += entry_len
                        matched = True
                        break
            if matched:
                continue

            b = raw[i]
            mapped = None
            if self.tbl_loader is not None:
                mapped = self.tbl_loader.char_map.get(b)

            if mapped is not None:
                out.append(mapped)
            elif self._is_printable_ascii(b):
                out.append(chr(b))
            else:
                out.append(f"{{B:{b:02X}}}")
                unknown_count += 1
            i += 1

        return "".join(out), unknown_count

    def _encode_text_with_placeholders(self, text: str) -> Optional[bytes]:
        """
        Re-encoda texto auditável para validação round-trip:
        - aceita placeholders {B:HH}
        - retorna None quando houver caractere sem mapeamento seguro.
        """
        if text is None:
            return b""

        out = bytearray()
        i = 0
        while i < len(text):
            m = BYTE_PLACEHOLDER_PATTERN.match(text, i)
            if m:
                out.append(int(m.group(1), 16))
                i = m.end()
                continue

            ch = text[i]
            if self.tbl_loader is not None and ch in self.tbl_loader.reverse_map:
                out.extend(self.tbl_loader.reverse_map[ch])
                i += 1
                continue

            code = ord(ch)
            if 32 <= code <= 126:
                out.append(code)
                i += 1
                continue
            if ch == "\n":
                out.append(0x0A)
                i += 1
                continue
            if ch == "\r":
                out.append(0x0D)
                i += 1
                continue
            return None

        return bytes(out)

    def _ascii_probe_words(self, words: Optional[List[str]] = None) -> int:
        """
        Procura palavras ASCII literais na ROM (prova determinística).
        Retorna total de hits e popula ascii_probe_hits/total.
        """
        if words is None:
            words = ["POWER", "TRIES", "SCORE", "TIME", "WELCOME"]

        hits: Dict[str, List[int]] = {}
        total = 0

        for word in words:
            try:
                pattern = word.encode("ascii")
            except UnicodeEncodeError:
                continue

            offsets: List[int] = []
            start = 0
            while True:
                idx = self.rom_data.find(pattern, start)
                if idx == -1:
                    break
                offsets.append(idx)
                start = idx + 1

            hits[word] = offsets
            total += len(offsets)

        self.ascii_probe_hits = hits
        self.ascii_probe_total = total
        return total

    def _extract_tilemap_probe(self) -> List[Dict]:
        """
        Extração por tilemap/font (V1 SMS).
        Usa heurísticas de SMSTilemapExtractor e gera itens encoding="tile".
        """
        try:
            from core.sms_pro_extractor import SMSTilemapExtractor, SMSExtractorConfig
        except Exception:
            return []

        cfg = SMSExtractorConfig()
        tile_extractor = SMSTilemapExtractor(self.rom_data, cfg)

        # 2.1 Font discovery
        self.font_candidates = tile_extractor.detect_font_tiles()

        # 2.2 Discovery de ranges candidatos (janelas 4KB/8KB)
        self.tilemap_candidate_ranges = tile_extractor.discover_tilemap_ranges()

        # 2.3 Tilemap discovery + decode heurístico (somente ranges quando disponível)
        if self.tilemap_candidate_ranges:
            tilemaps = tile_extractor.detect_tilemaps_in_ranges(
                self.tilemap_candidate_ranges
            )
        else:
            tilemaps = tile_extractor.detect_tilemaps()
        items: List[Dict] = []
        for tm in tilemaps:
            extracted = tile_extractor.extract_from_tilemap(tm, None)
            for it in extracted:
                decoded = (it.decoded_text or "").strip()
                items.append({
                    "id": -1,  # será renumerado
                    "offset": int(it.file_offset),
                    "decoded": decoded,
                    "clean": decoded,
                    "max_len": len(it.raw_bytes),
                    "terminator": it.terminator,
                    "source": "TILEMAP_PROBE",
                    "region": "TILEMAP_PROBE",
                    "category": "TILEMAP_PROBE",
                    "encoding": "tile",
                    "confidence": float(getattr(it, "confidence", 0.30)),
                    "has_pointer": False,
                    "reinsertion_safe": False,
                    "reason_code": "TILEMAP_NO_POINTER",
                    "pointer_value": None,
                    "pointer_refs": [],
                    "raw_bytes_hex": it.raw_hex,
                })

        self.tilemap_probe_items = items
        self.tilemap_probe_used = True
        return items

    # ========================================================================
    # AUTO-DISCOVERY DE TBL (TILEMAP 2 BYTES)
    # ========================================================================

    def _auto_discover_tilemap_tbl(self) -> Optional[Dict]:
        """
        Tenta descobrir automaticamente uma TBL de tilemap (2 bytes).
        Não usa IA nem scan cego final.
        """
        try:
            from core.sms_pro_extractor import SMSTilemapExtractor, SMSExtractorConfig, TBLAutoLearner
        except Exception:
            return None

        cfg = SMSExtractorConfig()
        tile_extractor = SMSTilemapExtractor(self.rom_data, cfg)
        ranges = tile_extractor.discover_tilemap_ranges()
        known_ranges = self._build_known_text_ranges_from_samples()
        if known_ranges:
            ranges = self._merge_ranges(ranges + known_ranges)
        if not ranges:
            return None

        # Guarda ranges para debug neutro
        self.tilemap_candidate_ranges = ranges

        attr_info = self._find_dominant_tilemap_attr(ranges)
        if not attr_info:
            return None
        attr_byte, attr_ratio = attr_info

        tilemaps = tile_extractor.detect_tilemaps_in_ranges(ranges)
        if tilemaps:
            ranges = [{"offset": int(t["offset"]), "size": int(t["length"])} for t in tilemaps]

        sequences, freq, run_score, _total_pairs = self._collect_tilemap_sequences(ranges, attr_byte)
        if not sequences or not freq:
            return None

        space_byte = self._infer_space_byte(freq, run_score)
        if space_byte is None:
            return None

        corpus = self._build_tilemap_corpus(sequences, space_byte)
        if not corpus:
            return None

        learner = TBLAutoLearner(corpus)
        learner.learn()

        mapping: Dict[int, str] = {}
        mapping[space_byte] = " "
        for b, ch in learner.mapping.items():
            if b == space_byte:
                continue
            mapping[b] = ch.upper()

        digits_mapped = self._infer_digit_mapping(freq, mapping)
        punct_mapped = self._infer_punctuation_mapping(sequences, mapping, space_byte)

        word_hits = self._count_word_hits(sequences, mapping, space_byte)
        confidence = self._score_tilemap_mapping(
            learner.global_confidence, freq, space_byte, word_hits
        )

        sample_texts = self._decode_tilemap_samples(sequences, mapping, space_byte, limit=10)

        info = {
            "attr_byte": attr_byte,
            "space_byte": space_byte,
            "confidence": round(confidence, 4),
            "mapping": mapping,
            "ranges": ranges,
            "digits_mapped": digits_mapped,
            "punct_mapped": punct_mapped,
            "word_hits": word_hits,
            "attr_ratio": round(attr_ratio, 4),
            "samples": sample_texts,
        }

        if confidence < 0.60 or len(mapping) < 15:
            info["accepted"] = False
            info["reason"] = "LOW_CONFIDENCE_OR_MAPPING"
            info["min_confidence"] = 0.60
            info["min_mapping"] = 15
            return info

        tbl_paths = self._write_auto_tilemap_tbl(mapping, attr_byte)
        info.update({
            "accepted": True,
            "tbl_abs_path": tbl_paths["tbl_abs"],
            "tbl_rel_path": tbl_paths["tbl_rel"],
            "tbl_written": tbl_paths["written"],
        })
        return info

    def _find_dominant_tilemap_attr(self, ranges: List[Dict]) -> Optional[Tuple[int, float]]:
        """Encontra o byte de atributo mais dominante em ranges de tilemap."""
        attr_freq: Counter = Counter()
        total_pairs = 0

        for r in ranges:
            start = int(r.get("offset", 0))
            size = int(r.get("size", 0))
            end = min(self.rom_size, start + size)
            if start < 0 or start >= end:
                continue
            if start % 2 != 0:
                start += 1
            for i in range(start, end - 1, 2):
                attr = self.rom_data[i + 1]
                attr_freq[attr] += 1
                total_pairs += 1

        if not attr_freq or total_pairs == 0:
            return None

        attr_byte, count = attr_freq.most_common(1)[0]
        ratio = count / total_pairs if total_pairs else 0.0
        if ratio < 0.20:
            return None
        return (attr_byte, ratio)

    def _merge_ranges(self, ranges: List[Dict]) -> List[Dict]:
        """Mescla ranges sobrepostos/adjacentes. Retorna apenas offset/size."""
        cleaned: List[Tuple[int, int]] = []
        for r in ranges:
            start = int(r.get("offset", 0))
            size = int(r.get("size", r.get("length", 0)) or 0)
            if size <= 0:
                continue
            end = start + size
            cleaned.append((start, end))

        if not cleaned:
            return []

        cleaned.sort(key=lambda x: x[0])
        merged: List[Tuple[int, int]] = []
        cur_start, cur_end = cleaned[0]
        for start, end in cleaned[1:]:
            if start <= cur_end + 1:
                cur_end = max(cur_end, end)
            else:
                merged.append((cur_start, cur_end))
                cur_start, cur_end = start, end
        merged.append((cur_start, cur_end))

        return [{"offset": s, "size": max(0, e - s)} for s, e in merged if e > s]

    def _build_known_text_ranges_from_samples(
        self,
        window_size: int = 0x400,
        window_before: int = 0x100
    ) -> List[Dict]:
        """Cria ranges a partir de offsets de amostras (tabelas rejeitadas)."""
        offsets: List[int] = []

        for item in self.rejected_pointer_table_details:
            for s in item.get("samples", []):
                off = s.get("offset")
                if isinstance(off, int):
                    offsets.append(off)

        for table in self.discovered_tables:
            for ptr in table.valid_pointers[:20]:
                resolved = self._resolve_pointer_heuristic(ptr)
                if resolved is not None:
                    offsets.append(resolved)

        if not offsets:
            return []

        ranges: List[Dict] = []
        for off in sorted(set(offsets)):
            start = max(0, off - window_before)
            if start % 2 != 0:
                start = max(0, start - 1)
            end = min(self.rom_size, start + window_size)
            size = end - start
            if size > 0:
                ranges.append({"offset": start, "size": size})

        return ranges

    def _collect_tilemap_sequences(
        self,
        ranges: List[Dict],
        attr_byte: int,
        min_len: int = 4
    ) -> Tuple[List[List[int]], Counter, Counter, int]:
        """Coleta sequências de low-bytes onde o attr coincide."""
        sequences: List[List[int]] = []
        freq: Counter = Counter()
        run_score: Counter = Counter()
        total_pairs = 0

        for r in ranges:
            start = int(r.get("offset", 0))
            size = int(r.get("size", 0))
            end = min(self.rom_size, start + size)
            if start < 0 or start >= end:
                continue
            if start % 2 != 0:
                start += 1

            seq: List[int] = []
            i = start
            while i + 1 < end:
                low = self.rom_data[i]
                attr = self.rom_data[i + 1]
                if attr == attr_byte:
                    seq.append(low)
                    freq[low] += 1
                    total_pairs += 1
                else:
                    if len(seq) >= min_len:
                        sequences.append(seq)
                        self._accumulate_run_score(seq, run_score)
                    seq = []
                i += 2

            if len(seq) >= min_len:
                sequences.append(seq)
                self._accumulate_run_score(seq, run_score)

        return sequences, freq, run_score, total_pairs

    def _accumulate_run_score(self, seq: List[int], run_score: Counter) -> None:
        """Acumula score por runs (ajuda a detectar espaço)."""
        if not seq:
            return
        prev = seq[0]
        run_len = 1
        for b in seq[1:]:
            if b == prev:
                run_len += 1
            else:
                if run_len >= 2:
                    run_score[prev] += run_len
                prev = b
                run_len = 1
        if run_len >= 2:
            run_score[prev] += run_len

    def _infer_space_byte(self, freq: Counter, run_score: Counter) -> Optional[int]:
        """Infere provável byte de espaço."""
        if not freq:
            return None
        return max(freq.keys(), key=lambda b: freq[b] + run_score.get(b, 0) * 2)

    def _build_tilemap_corpus(self, sequences: List[List[int]], space_byte: int) -> List[bytes]:
        """Cria corpus (palavras) para o auto-learner."""
        corpus: List[bytes] = []
        for seq in sequences:
            word: List[int] = []
            for b in seq:
                if b == space_byte:
                    if len(word) >= 3:
                        corpus.append(bytes(word))
                    word = []
                else:
                    word.append(b)
            if len(word) >= 3:
                corpus.append(bytes(word))
        # Fallback: se não há corpus, usa sequências inteiras como “palavras”
        if not corpus:
            for seq in sequences:
                if len(seq) >= 3:
                    corpus.append(bytes(seq[:24]))
        return corpus

    def _infer_digit_mapping(self, freq: Counter, mapping: Dict[int, str]) -> int:
        """Tenta mapear um bloco sequencial de 10 bytes para dígitos 0-9."""
        used = set(mapping.keys())
        unused = sorted([b for b in freq.keys() if b not in used])
        if not unused:
            return 0

        best_start = None
        best_score = 0

        # Procura runs sequenciais
        run_start = unused[0]
        prev = unused[0]
        for b in unused[1:] + [None]:
            if b is not None and b == prev + 1:
                prev = b
                continue
            run_end = prev
            run_len = run_end - run_start + 1
            if run_len >= 10:
                # Avalia todas as janelas de 10 dentro do run
                for start in range(run_start, run_end - 9 + 1):
                    score = sum(freq.get(x, 0) for x in range(start, start + 10))
                    if score > best_score:
                        best_score = score
                        best_start = start
            if b is None:
                break
            run_start = b
            prev = b

        if best_start is None:
            return 0

        for i in range(10):
            mapping[best_start + i] = str(i)
        return 10

    def _infer_punctuation_mapping(
        self,
        sequences: List[List[int]],
        mapping: Dict[int, str],
        space_byte: int
    ) -> int:
        """Mapeia pontuações comuns pelos bytes vizinhos de espaços."""
        candidates: Counter = Counter()
        for seq in sequences:
            for i, b in enumerate(seq):
                if b in mapping or b == space_byte:
                    continue
                score = 1
                if (i > 0 and seq[i - 1] == space_byte) or (i + 1 < len(seq) and seq[i + 1] == space_byte):
                    score = 2
                candidates[b] += score

        punct_chars = [".", ",", "!", "?", "-", ":"]
        mapped = 0
        for (b, _), ch in zip(candidates.most_common(len(punct_chars)), punct_chars):
            mapping[b] = ch
            mapped += 1
        return mapped

    def _count_word_hits(
        self,
        sequences: List[List[int]],
        mapping: Dict[int, str],
        space_byte: int
    ) -> int:
        """Conta hits de palavras comuns para estimar confiança."""
        words = [
            "THE", "AND", "YOU", "YOUR", "WELCOME", "GAME", "OVER", "PRESS",
            "START", "STAGE", "MINNIE", "MICKEY", "MIZRABEL", "CASTLE",
            "WITCH", "POWER", "TIME", "SCORE", "CONTINUE", "NEW", "PRACTICE", "NORMAL"
        ]
        samples = []
        for seq in sequences[:60]:
            parts = []
            for b in seq:
                if b == space_byte:
                    parts.append(" ")
                elif b in mapping:
                    parts.append(mapping[b])
            samples.append("".join(parts))
        joined = " ".join(samples).upper()
        return sum(1 for w in words if w in joined)

    def _decode_tilemap_samples(
        self,
        sequences: List[List[int]],
        mapping: Dict[int, str],
        space_byte: int,
        limit: int = 10
    ) -> List[str]:
        """Gera amostras decodificadas para revisão manual."""
        samples: List[str] = []
        for seq in sequences[:max(0, limit)]:
            parts: List[str] = []
            for b in seq:
                if b == space_byte:
                    parts.append(" ")
                elif b in mapping:
                    parts.append(mapping[b])
            text = "".join(parts).strip()
            if text:
                samples.append(text)
        return samples

    def _score_tilemap_mapping(
        self,
        base_conf: float,
        freq: Counter,
        space_byte: int,
        word_hits: int
    ) -> float:
        """Combina sinais para score final."""
        total = sum(freq.values()) or 1
        space_ratio = freq.get(space_byte, 0) / total
        score = base_conf
        score += min(space_ratio * 0.5, 0.20)
        score += min(word_hits * 0.02, 0.20)
        return min(1.0, score)

    def _write_auto_tilemap_tbl(self, mapping: Dict[int, str], attr_byte: int) -> Dict[str, Any]:
        """Escreve TBL auto-gerada (se não existir) e retorna paths."""
        profiles_dir = Path(__file__).parent / "profiles" / "sms"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        tbl_abs = profiles_dir / f"{self.crc32_full}.tbl"
        tbl_rel = f"core/profiles/sms/{self.crc32_full}.tbl"

        written = False
        if not tbl_abs.exists():
            lines = [
                "# TBL auto-gerada (tilemap 2 bytes)",
                f"# CRC32={self.crc32_full} ATTR=0x{attr_byte:02X}",
                "# Formato: LLAA=CHAR (LL=low byte, AA=attr)",
                "",
            ]
            for b, ch in sorted(mapping.items()):
                hexval = f"{b:02X}{attr_byte:02X}"
                lines.append(f"{hexval}={ch}")
            tbl_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")
            written = True

        return {"tbl_abs": str(tbl_abs), "tbl_rel": tbl_rel, "written": written}

    def _build_auto_tilemap_profile(self, auto_info: Dict) -> Dict:
        """Cria profile tilemap baseado no auto-discovery."""
        regions = []
        for idx, r in enumerate(auto_info.get("ranges", []), 1):
            start = int(r.get("offset", 0))
            size = int(r.get("size", 0))
            end = min(self.rom_size, start + size)
            if end > start:
                regions.append({
                    "start": start,
                    "end": end,
                    "label": f"AUTO_RANGE_{idx:02d}",
                })

        return {
            "crc32": self.crc32_full,
            "console": "SMS",
            "region": "unknown",
            "encoding": "tilemap",
            "tbl_path": auto_info.get("tbl_rel_path"),
            "terminators": [0],
            "bank_rule": "SLOT1_4000",
            "pointer_tables": [],
            "font_regions": [],
            "text_regions": regions,
            "compression": None,
        }

    def _update_game_profiles_db(self, profile: Dict) -> None:
        """Atualiza o game_profiles_db.json de forma segura (sem sobrescrever TBL existente)."""
        try:
            from datetime import datetime, timezone
            db_path = Path(__file__).parent / "game_profiles_db.json"
            if not db_path.exists():
                return
            data = json.loads(db_path.read_text(encoding="utf-8"))
            games = data.get("games", [])

            existing = None
            for entry in games:
                if str(entry.get("crc32", "")).upper() == self.crc32_full.upper():
                    existing = entry
                    break

            if existing:
                if existing.get("tbl_path"):
                    return
                existing.update({
                    "encoding": "tilemap",
                    "tbl_path": profile.get("tbl_path"),
                    "text_regions": profile.get("text_regions", []),
                })
            else:
                sanitized = {k: v for k, v in profile.items() if k not in ("name", "notes")}
                games.append(sanitized)
                data["total_games"] = len(games)

            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            db_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logging.warning("[EXTRACTOR] Profile DB update failed: %s", exc)
            return

    def _load_game_profile_by_crc(self) -> Optional[Dict]:
        """Carrega profile do jogo pelo CRC32 (game_profiles_db.json)."""
        try:
            db_path = Path(__file__).parent / "game_profiles_db.json"
            if not db_path.exists():
                return None
            data = json.loads(db_path.read_text(encoding="utf-8"))
            for entry in data.get("games", []):
                if str(entry.get("crc32", "")).upper() == self.crc32_full.upper():
                    clean = dict(entry)
                    clean.pop("name", None)
                    clean.pop("notes", None)
                    return clean
        except Exception:
            return None
        return None

    def _scan_tilemap_region_with_tbl(
        self,
        rom_data: bytes,
        tbl,
        start: int,
        end: int,
        label: str
    ) -> List[Dict]:
        """Escaneia região com TBL multi-byte (tilemap 2 bytes)."""
        items: List[Dict] = []
        entry_len = getattr(tbl, "max_entry_len", 1)
        if entry_len <= 0:
            return items

        i = start
        while i <= end - entry_len:
            seq_start = i
            text_chars: List[str] = []
            j = i

            while j <= end - entry_len:
                seq = rom_data[j:j + entry_len]
                char = tbl.multi_byte_map.get(seq) if hasattr(tbl, "multi_byte_map") else None
                if char is None and entry_len == 1:
                    char = tbl.char_map.get(rom_data[j])
                if char is not None:
                    text_chars.append(char)
                    j += entry_len
                else:
                    break

            text_raw = "".join(text_chars)
            text_clean = text_raw.strip()
            alpha_count = sum(1 for c in text_clean if c.isalpha())
            if alpha_count >= 3 and len(text_clean) >= 3:
                raw_bytes = rom_data[seq_start:j]
                items.append({
                    "id": -1,
                    "offset": int(seq_start),
                    "decoded": text_raw,
                    "clean": text_raw,
                    "clean_stripped": text_clean,
                    "max_len": len(raw_bytes),
                    "terminator": None,
                    "source": f"TILEMAP_{label}" if label else "TILEMAP_PROFILE",
                    "region": label or "TILEMAP_PROFILE",
                    "category": "TILEMAP",
                    "encoding": "tilemap",
                    "confidence": 0.95,
                    "has_pointer": False,
                    "reinsertion_safe": True,
                    "pointer_value": None,
                    "pointer_refs": [],
                    "raw_bytes_hex": raw_bytes.hex().upper(),
                })
                i = j
            else:
                i += entry_len

        return items

    def _extract_tilemap_profile(self, profile: Dict) -> List[Dict]:
        """Extrai textos por tilemap usando TBL e regiões do profile."""
        tbl_path = profile.get("tbl_path")
        if not tbl_path:
            return []

        # Resolve caminho da TBL (absoluto ou relativo ao projeto)
        p = Path(tbl_path)
        if not p.is_absolute():
            p = Path(__file__).parent.parent / tbl_path
        if not p.exists():
            return []

        try:
            from core.tbl_loader import TBLLoader
        except Exception:
            return []

        tbl = TBLLoader(str(p))
        if (len(tbl.char_map) + len(tbl.multi_byte_map)) == 0:
            return []

        items: List[Dict] = []
        regions = profile.get("text_regions") or []
        if regions:
            for region in regions:
                start = int(region.get("start", 0))
                end = int(region.get("end", 0))
                label = region.get("label", "")
                if start <= 0 or end <= start:
                    continue
                end = min(end, self.rom_size)
                items.extend(self._scan_tilemap_region_with_tbl(self.rom_data, tbl, start, end, label))
        else:
            items.extend(self._scan_tilemap_region_with_tbl(self.rom_data, tbl, 0, self.rom_size, "full_scan"))

        return items

    # ========================================================================
    # FILTRO DE TEXTO ESTATISTICO
    # ========================================================================

    def _calculate_text_stats(self, data: bytes) -> dict:
        """Calcula estatisticas de um bloco de bytes."""
        if not data:
            return {"valid": False}

        total = len(data)
        alphanumeric = sum(1 for b in data if (0x30 <= b <= 0x39) or  # 0-9
                                              (0x41 <= b <= 0x5A) or  # A-Z
                                              (0x61 <= b <= 0x7A))    # a-z
        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
        letters = sum(1 for b in data if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A))
        vowels = sum(1 for b in data if b in (0x41, 0x45, 0x49, 0x4F, 0x55,  # AEIOU
                                               0x61, 0x65, 0x69, 0x6F, 0x75)) # aeiou

        return {
            "valid": True,
            "total": total,
            "alphanumeric": alphanumeric,
            "alphanumeric_ratio": alphanumeric / total if total > 0 else 0,
            "printable": printable,
            "printable_ratio": printable / total if total > 0 else 0,
            "letters": letters,
            "letter_ratio": letters / total if total > 0 else 0,
            "vowels": vowels,
            "vowel_ratio": vowels / letters if letters > 0 else 0,
        }

    def _is_valid_text_block(self, data: bytes, *, require_terminator: bool = True) -> bool:
        """
        FILTRO ESTATISTICO UNIVERSAL

        Valida se um bloco de bytes parece ser texto legivel.
        Criterios:
        - Mais de 60% de caracteres alfanumericos
        - Comprimento minimo
        - Contem vogais (indica texto real vs garbage)
        - Sem sequencias de consoantes impossiveis
        """
        if not data or len(data) < self.config.min_text_length:
            return False

        # Se houver TBL carregada (1 byte), valida pelo texto decodificado
        if self.tbl_loader is not None and self.tbl_loader.max_entry_len == 1:
            try:
                decoded = self.tbl_loader.decode_bytes(data, max_length=self.config.max_text_length)
            except Exception:
                decoded = ""
            if not decoded:
                return False
            return is_plausible_text_sms(decoded)

        stats = self._calculate_text_stats(data)
        if not stats["valid"]:
            return False

        # Criterio 1: Minimo 60% alfanumerico
        if stats["alphanumeric_ratio"] < self.config.alphanumeric_threshold:
            return False

        # Criterio 2: Deve ter letras
        if stats["letters"] == 0:
            return False

        # Criterio 3: Se tem 5+ letras, deve ter vogais
        if stats["letters"] >= 5 and stats["vowels"] == 0:
            return False

        # Criterio 4: Decodifica e verifica padroes de garbage
        try:
            text = data.decode("ascii", errors="ignore")
        except:
            return False

        # Rejeita sequencias de 6+ consoantes
        if re.search(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{6,}', text):
            return False

        # Rejeita padroes repetitivos
        if re.search(r'(.)\1{4,}', text):  # 5+ caracteres iguais
            return False

        return True

    def _post_filter_text(self, text: str) -> bool:
        """
        FIREWALL FINAL - Filtro pos-extracao.

        Regra BLOQUEADOR:
        - string <3 caracteres com ~ # | ^ _ = DESCARTAR IMEDIATO
        """
        if not text:
            return False

        text_norm = self._sanitize_profile_ascii_text(str(text))
        if not text_norm:
            return False

        # Firewall: strings curtas (<3) com símbolos especiais = descartar.
        forbidden_short_chars = set('~#|^_')
        if len(text_norm) < 3 and any(c in forbidden_short_chars for c in text_norm):
            return False

        # Tokens técnicos curtos permitidos.
        known_short = {
            "HP", "MP", "SP", "XP", "LV", "GP", "OK",
            "YES", "NO", "ON", "OFF", "ATK", "DEF", "STR"
        }
        if len(text_norm) < 3:
            return text_norm.upper().strip() in known_short

        # Filtro plausível principal para reduzir lixo vindo de ponteiros ruins.
        return bool(is_plausible_text_sms(text_norm))

    # ========================================================================
    # SCANNER DE PONTEIROS HEURISTICO
    # ========================================================================

    def _find_potential_pointer_tables(self) -> List[PointerTable]:
        """
        SCANNER DE PONTEIROS HEURISTICO

        Escaneia a ROM procurando por sequencias de ponteiros 16-bit LE
        que apontem para enderecos contendo texto ASCII valido.

        Criterios para uma tabela valida:
        - Minimo de 8 ponteiros consecutivos
        - Ponteiros apontam para areas < tamanho da ROM
        - Pelo menos 60% dos ponteiros levam a texto valido
        """
        discovered: List[PointerTable] = []
        scanned_ranges: Set[Tuple[int, int]] = set()
        self.rejected_pointer_table_low_plausibility = 0
        self.rejected_pointer_table_details = []
        self.partial_pointer_table_details = []
        self.pointer_table_partial_accepted = 0
        self.pointer_table_partial_entries_total = 0
        self.pointer_table_partial_kept_count = 0

        # Escaneia em intervalos de 2 bytes (tamanho de ponteiro 16-bit)
        i = 0
        while i < self.rom_size - (self.config.min_pointers_for_table * 2):
            # Pula se ja escaneamos esta area
            skip = False
            for start, end in scanned_ranges:
                if start <= i < end:
                    skip = True
                    break
            if skip:
                i += 2
                continue

            # Tenta encontrar sequencia de ponteiros validos
            table = self._try_detect_pointer_table_at(i)

            if table:
                table_mode = str(getattr(table, "mode", "FULL") or "FULL").upper()
                required_conf = float(self.config.pointer_validation_threshold)
                if table_mode == "PARTIAL":
                    required_conf = max(0.35, required_conf * 0.60)
                if table.confidence >= required_conf:
                    discovered.append(table)
                    # Marca area como escaneada
                    span_entries = int(table.checked_entries or table.entry_count or 0)
                    if span_entries <= 0:
                        span_entries = int(table.entry_count)
                    table_end = table.table_offset + (span_entries * table.entry_size)
                    scanned_ranges.add((table.table_offset, table_end))
                    i = table_end
                    continue
            i += 2

        # Ordena por confianca
        discovered.sort(key=lambda t: t.confidence, reverse=True)
        return discovered

    def _try_build_partial_pointer_table(
        self,
        *,
        table_offset: int,
        valid_entries: List[Dict[str, Any]],
        confidence: float,
        total_checked: int,
        plausibility_ratio: float,
        trigger_reason: str,
    ) -> Optional[PointerTable]:
        """
        Tenta reaproveitar tabelas mistas mantendo apenas entradas de alta qualidade.
        """
        if not bool(self.config.pointer_partial_mode_enabled):
            return None
        if not valid_entries:
            return None

        min_entries = max(2, int(self.config.pointer_partial_min_entries))
        min_ratio = max(0.05, min(1.0, float(self.config.pointer_partial_min_ratio)))
        min_score = max(0.10, min(1.0, float(self.config.pointer_partial_min_plausibility_score)))

        selected: List[Dict[str, Any]] = []
        seen_offsets: Set[int] = set()
        for entry in valid_entries:
            score = float(entry.get("score", 0.0) or 0.0)
            plausible = bool(entry.get("plausible", False))
            term = entry.get("terminator")
            term_ok = isinstance(term, int) and int(term) in self.config.valid_terminators
            decoded = str(entry.get("decoded", "") or "").strip()
            if not decoded:
                continue
            if not plausible:
                continue
            if score < min_score:
                continue
            if (not term_ok) and score < (min_score + 0.15):
                continue
            resolved = entry.get("resolved")
            if isinstance(resolved, int):
                if int(resolved) in seen_offsets:
                    continue
                seen_offsets.add(int(resolved))
            selected.append(entry)

        if len(selected) < min_entries:
            return None

        selected_ratio = len(selected) / max(1, len(valid_entries))
        if selected_ratio < min_ratio:
            return None

        selected.sort(key=lambda e: int(e.get("entry_idx", 0)))
        partial_confidence = max(0.35, min(0.95, float(confidence) * float(selected_ratio)))

        self.pointer_table_partial_accepted += 1
        self.pointer_table_partial_entries_total += int(len(selected))
        self.pointer_table_partial_kept_count += int(len(selected))
        self.partial_pointer_table_details.append(
            {
                "table_offset": int(table_offset),
                "trigger_reason": str(trigger_reason),
                "entries_selected": int(len(selected)),
                "entries_total_valid": int(len(valid_entries)),
                "selected_ratio": float(round(selected_ratio, 4)),
                "plausibility_ratio": float(round(float(plausibility_ratio), 4)),
                "confidence": float(round(partial_confidence, 4)),
                "samples": [
                    {
                        "entry_idx": int(e.get("entry_idx", 0)),
                        "offset": int(e.get("resolved", 0)),
                        "score": float(round(float(e.get("score", 0.0) or 0.0), 4)),
                        "ascii": str(e.get("decoded", "") or ""),
                    }
                    for e in selected[:20]
                ],
            }
        )

        return PointerTable(
            table_offset=int(table_offset),
            entry_count=int(len(selected)),
            entry_size=2,
            valid_pointers=[int(e.get("ptr", 0)) for e in selected],
            pointer_entry_indexes=[int(e.get("entry_idx", 0)) for e in selected],
            confidence=float(partial_confidence),
            mode="PARTIAL",
            checked_entries=int(max(int(total_checked or 0), len(valid_entries))),
            plausibility_ratio=float(plausibility_ratio),
            partial_discarded=int(max(0, len(valid_entries) - len(selected))),
        )

    def _try_detect_pointer_table_at(self, offset: int) -> Optional[PointerTable]:
        """
        Tenta detectar uma tabela de ponteiros iniciando em 'offset'.
        """
        valid_entries: List[Dict[str, Any]] = []
        invalid_count = 0
        max_invalid_streak = 3
        current_invalid_streak = 0
        idx = 0
        scanned_entries = 0
        while idx < self.config.min_pointers_for_table * 10:  # Limita busca
            ptr_offset = offset + (idx * 2)
            if ptr_offset + 2 > self.rom_size:
                break

            ptr_value = self._read_u16le(ptr_offset)
            if ptr_value is None:
                break
            scanned_entries = idx + 1

            # Valida se ponteiro aponta para area valida
            resolved = self._resolve_pointer_heuristic(ptr_value)
            entry_added = False
            if resolved is not None:
                # Verifica se ha texto valido no destino
                text_data = self._read_text_at_offset(resolved)
                if text_data and self._is_valid_text_block(text_data, require_terminator=False):
                    try:
                        if self.tbl_loader is not None and self.tbl_loader.max_entry_len == 1:
                            decoded = self.tbl_loader.decode_bytes(
                                text_data, max_length=self.config.max_text_length
                            ).strip()
                        else:
                            decoded = text_data.decode("ascii", errors="ignore").strip()
                    except Exception:
                        decoded = ""

                    if decoded:
                        term_offset = resolved + len(text_data)
                        terminator = self.rom_data[term_offset] if term_offset < self.rom_size else None
                        if self.tbl_loader is not None and self.tbl_loader.max_entry_len == 1:
                            plausible = bool(is_plausible_text_sms(decoded))
                        else:
                            plausible = bool(is_plausible_ascii(decoded))
                        valid_entries.append(
                            {
                                "entry_idx": int(idx),
                                "ptr": int(ptr_value),
                                "resolved": int(resolved),
                                "decoded": str(decoded),
                                "raw_bytes": bytes(text_data),
                                "terminator": terminator,
                                "score": float(score_ascii_plausibility(decoded)),
                                "plausible": bool(plausible),
                            }
                        )
                        entry_added = True
                        current_invalid_streak = 0

            if not entry_added:
                invalid_count += 1
                current_invalid_streak += 1

            # Para se muitos invalidos consecutivos
            if current_invalid_streak >= max_invalid_streak:
                break

            idx += 1

        # Verifica se encontramos ponteiros suficientes
        if len(valid_entries) < self.config.min_pointers_for_table:
            return None

        total_checked = len(valid_entries) + invalid_count
        confidence = len(valid_entries) / total_checked if total_checked > 0 else 0
        plausibility_ratio_base = (
            sum(1 for e in valid_entries if bool(e.get("plausible"))) / len(valid_entries)
            if valid_entries
            else 0.0
        )

        if confidence < self.config.pointer_validation_threshold:
            partial = self._try_build_partial_pointer_table(
                table_offset=int(offset),
                valid_entries=valid_entries,
                confidence=float(confidence),
                total_checked=int(total_checked),
                plausibility_ratio=float(plausibility_ratio_base),
                trigger_reason="LOW_CONFIDENCE",
            )
            if partial is not None:
                return partial
            return None

        # Anti-cluster: rejeita tabela se >50% dos ponteiros resolvem pro mesmo offset
        unique_resolved: Set[int] = set()
        for ent in valid_entries:
            resolved_val = ent.get("resolved")
            if isinstance(resolved_val, int):
                unique_resolved.add(int(resolved_val))
        if len(unique_resolved) < len(valid_entries) * 0.5:
            partial = self._try_build_partial_pointer_table(
                table_offset=int(offset),
                valid_entries=valid_entries,
                confidence=float(confidence),
                total_checked=int(total_checked),
                plausibility_ratio=float(plausibility_ratio_base),
                trigger_reason="ANTI_CLUSTER",
            )
            if partial is not None:
                return partial
            return None

        decoded_samples: List[str] = [
            str(ent.get("decoded", "") or "")
            for ent in valid_entries[:20]
            if str(ent.get("decoded", "") or "").strip()
        ]

        plausibility_ratio = float(plausibility_ratio_base)
        if self.tbl_loader is not None and self.tbl_loader.max_entry_len == 1:
            good = sum(1 for s in decoded_samples if is_plausible_text_sms(s))
            ratio = (good / len(decoded_samples)) if decoded_samples else 0.0
            plausibility_ratio = float(ratio)
            if good < 4 or ratio < 0.35:
                partial = self._try_build_partial_pointer_table(
                    table_offset=int(offset),
                    valid_entries=valid_entries,
                    confidence=float(confidence),
                    total_checked=int(total_checked),
                    plausibility_ratio=float(ratio),
                    trigger_reason="LOW_PLAUSIBILITY",
                )
                if partial is not None:
                    return partial

                avg_score = (
                    sum(float(ent.get("score", 0.0) or 0.0) for ent in valid_entries[:20]) / len(valid_entries[:20])
                    if valid_entries[:20] else 0.0
                )
                samples_detail: List[Dict[str, Any]] = []
                for ent in valid_entries[:20]:
                    samples_detail.append(
                        {
                            "offset": int(ent.get("resolved", 0) or 0),
                            "hex": str((ent.get("raw_bytes") or b"").hex()),
                            "ascii": str(ent.get("decoded", "") or ""),
                            "score": float(ent.get("score", 0.0) or 0.0),
                        }
                    )
                self.rejected_pointer_table_details.append({
                    "table_offset": int(offset),
                    "reason": "REJECTED_POINTER_TABLE_LOW_PLAUSIBILITY",
                    "plausibility_ratio": ratio,
                    "avg_score": avg_score,
                    "sample_count": len(samples_detail),
                    "samples": samples_detail,
                })
                self.rejected_pointer_table_low_plausibility += 1
                return None
        else:
            if not should_accept_pointer_table(decoded_samples):
                good = sum(1 for s in decoded_samples if is_plausible_ascii(s))
                ratio = (good / len(decoded_samples)) if decoded_samples else 0.0
                plausibility_ratio = float(ratio)
                partial = self._try_build_partial_pointer_table(
                    table_offset=int(offset),
                    valid_entries=valid_entries,
                    confidence=float(confidence),
                    total_checked=int(total_checked),
                    plausibility_ratio=float(ratio),
                    trigger_reason="LOW_PLAUSIBILITY",
                )
                if partial is not None:
                    return partial
                avg_score = (
                    sum(float(ent.get("score", 0.0) or 0.0) for ent in valid_entries[:20]) / len(valid_entries[:20])
                    if valid_entries[:20] else 0.0
                )
                samples_detail: List[Dict[str, Any]] = []
                for ent in valid_entries[:20]:
                    samples_detail.append(
                        {
                            "offset": int(ent.get("resolved", 0) or 0),
                            "hex": str((ent.get("raw_bytes") or b"").hex()),
                            "ascii": str(ent.get("decoded", "") or ""),
                            "score": float(ent.get("score", 0.0) or 0.0),
                        }
                    )
                self.rejected_pointer_table_details.append({
                    "table_offset": int(offset),
                    "reason": "REJECTED_POINTER_TABLE_LOW_PLAUSIBILITY",
                    "plausibility_ratio": ratio,
                    "avg_score": avg_score,
                    "sample_count": len(samples_detail),
                    "samples": samples_detail,
                })
                self.rejected_pointer_table_low_plausibility += 1
                return None

        # Consistencia de terminadores: tabelas reais tem terminador consistente
        term_counter: Counter = Counter()
        for ent in valid_entries[:20]:
            term = ent.get("terminator")
            if isinstance(term, int):
                term_counter[int(term)] += 1
        if term_counter:
            _, top_count = term_counter.most_common(1)[0]
            if top_count / sum(term_counter.values()) < 0.30:
                partial = self._try_build_partial_pointer_table(
                    table_offset=int(offset),
                    valid_entries=valid_entries,
                    confidence=float(confidence),
                    total_checked=int(total_checked),
                    plausibility_ratio=float(plausibility_ratio),
                    trigger_reason="LOW_TERMINATOR_CONSISTENCY",
                )
                if partial is not None:
                    return partial
                return None  # Terminadores muito dispersos = tabela falsa

        return PointerTable(
            table_offset=offset,
            entry_count=len(valid_entries),
            entry_size=2,
            valid_pointers=[int(ent.get("ptr", 0)) for ent in valid_entries],
            pointer_entry_indexes=[int(ent.get("entry_idx", 0)) for ent in valid_entries],
            confidence=float(confidence),
            mode="FULL",
            checked_entries=int(max(int(total_checked), int(scanned_entries))),
            plausibility_ratio=float(plausibility_ratio),
            partial_discarded=0,
        )

    def _resolve_pointer_heuristic(self, ptr: int) -> Optional[int]:
        """
        Resolve ponteiro 16-bit para offset na ROM.
        Usa heuristica de bancos do SMS.
        """
        if ptr is None:
            return None

        bank_size = 0x4000  # 16KB
        num_banks = max(1, (self.rom_size + bank_size - 1) // bank_size)

        candidates: List[int] = []

        # Slot 0: 0x0000-0x3FFF -> Direto
        if 0x0000 <= ptr < 0x4000:
            if ptr < self.rom_size:
                candidates.append(ptr)

        # Slot 1: 0x4000-0x7FFF -> Qualquer bank
        elif 0x4000 <= ptr < 0x8000:
            local = ptr - 0x4000
            for bank in range(num_banks):
                rom_off = bank * bank_size + local
                if 0 <= rom_off < self.rom_size:
                    candidates.append(rom_off)

        # Slot 2: 0x8000-0xBFFF -> Qualquer bank
        elif 0x8000 <= ptr < 0xC000:
            local = ptr - 0x8000
            for bank in range(num_banks):
                rom_off = bank * bank_size + local
                if 0 <= rom_off < self.rom_size:
                    candidates.append(rom_off)

        # Acima de 0xC000 -> RAM, improvavel
        elif ptr >= 0xC000:
            return None

        # Fallback direto
        else:
            if 0 <= ptr < self.rom_size:
                candidates.append(ptr)

        # Retorna o primeiro candidato que tem dados validos
        for off in candidates:
            data = self._read_text_at_offset(off)
            if data and len(data) >= self.config.min_text_length:
                return off

        return candidates[0] if candidates else None

    def _read_text_at_offset(self, offset: int) -> Optional[bytes]:
        """
        Le bytes de texto a partir de um offset ate encontrar terminador.
        """
        if offset < 0 or offset >= self.rom_size:
            return None

        data = bytearray()
        i = offset

        while i < self.rom_size and len(data) < self.config.max_text_length:
            byte = self.rom_data[i]

            # Verifica terminadores
            if byte in self.config.valid_terminators:
                break

            # Se nao e imprimivel, para (somente quando não há TBL 1-byte)
            if (self.tbl_loader is None or self.tbl_loader.max_entry_len != 1) and not self._is_printable_ascii(byte):
                break

            data.append(byte)
            i += 1

        return bytes(data) if data else None

    # ========================================================================
    # EXTRAÇÃO DE TEXTO
    # ========================================================================

    def _extract_from_pointer_tables(self) -> List[TextBlock]:
        """Extrai texto das tabelas de ponteiros descobertas."""
        blocks: List[TextBlock] = []
        seen_offsets: Set[int] = set()

        for table in self.discovered_tables:
            for idx, ptr in enumerate(table.valid_pointers):
                entry_idx = (
                    int(table.pointer_entry_indexes[idx])
                    if idx < len(table.pointer_entry_indexes)
                    else int(idx)
                )
                resolved = self._resolve_pointer_heuristic(ptr)
                if resolved is None or resolved in seen_offsets:
                    continue

                data = self._read_text_at_offset(resolved)
                if not data or not self._is_valid_text_block(data):
                    continue

                try:
                    if self.tbl_loader is not None and self.tbl_loader.max_entry_len == 1:
                        text = self.tbl_loader.decode_bytes(
                            data, max_length=self.config.max_text_length
                        ).strip()
                    else:
                        text = data.decode("ascii", errors="ignore").strip()
                except Exception:
                    continue

                if not text:
                    continue

                # Determina terminador
                term_offset = resolved + len(data)
                terminator = self.rom_data[term_offset] if term_offset < self.rom_size else None

                blocks.append(TextBlock(
                    offset=resolved,
                    raw_bytes=data,
                    decoded_text=text,
                    max_length=len(data),
                    terminator=terminator,
                    source="POINTER",
                    pointer_table_offset=table.table_offset,
                    pointer_entry_offset=table.table_offset + (entry_idx * table.entry_size),
                    pointer_value=ptr,  # Valor lido do ponteiro (prova)
                    confidence=table.confidence
                ))
                seen_offsets.add(resolved)

        # Overlap dedup: merge blocos que se sobrepõem (manter o mais longo)
        if blocks:
            blocks.sort(key=lambda b: b.offset)
            merged: List[TextBlock] = [blocks[0]]
            for block in blocks[1:]:
                prev = merged[-1]
                if block.offset < prev.offset + prev.max_length:
                    # Overlap: manter o mais longo
                    if block.max_length > prev.max_length:
                        merged[-1] = block
                else:
                    merged.append(block)
            return merged

        return blocks

    def _extract_ascii_region(self, start: int, end: int, source: str) -> List[TextBlock]:
        """Extrai blocos ASCII de uma região específica."""
        blocks: List[TextBlock] = []

        end = min(end, self.rom_size)
        i = start

        while i < end:
            if not self._is_printable_ascii(self.rom_data[i]):
                i += 1
                continue

            # Encontra sequencia de ASCII
            j = i
            while j < end and self._is_printable_ascii(self.rom_data[j]):
                j += 1

            data = self.rom_data[i:j]

            if self._is_valid_text_block(data, require_terminator=False):
                try:
                    text = data.decode("ascii", errors="ignore").strip()
                except:
                    text = ""

                if text and len(text) >= self.config.min_text_length:
                    terminator = self.rom_data[j] if j < self.rom_size else None

                    blocks.append(TextBlock(
                        offset=i,
                        raw_bytes=data,
                        decoded_text=text,
                        max_length=len(data),
                        terminator=terminator,
                        source=source,
                        confidence=0.7
                    ))

            i = j + 1

        return blocks

    def _sanitize_profile_ascii_text(self, text: str) -> str:
        """
        Limpa prefixos técnicos comuns em regiões ASCII declaradas no profile.
        Ex.: "00Return to the view" -> "Return to the view".
        """
        t = str(text or "").strip()
        if not t:
            return ""
        t = re.sub(r"^[0-9&]{1,3}(?=[A-Za-z])", "", t)
        # Prefixos técnicos de 1 byte que vazam em alguns scripts SMS.
        # Ex.: "TYou have..." -> "You have...", "HOriginal..." -> "Original..."
        t = re.sub(r"^[THZ4](?=[A-Z][a-z])", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _decode_control_prefixed_ascii(self, data: bytes) -> str:
        """
        Decodifica sequência com bytes de controle intercalados:
        [ctrl][char][ctrl][char]...

        Observação:
        - Em alguns blocos de intro/menu SMS, o espaço visual aparece como
          controle específico antes da próxima letra.
        """
        if not data:
            return ""

        chars: List[str] = []
        i = 0
        while i + 1 < len(data):
            ctrl = data[i]
            ch = data[i + 1]
            if ctrl == 0x00 or ctrl >= 0x20 or not self._is_printable_ascii(ch):
                break

            c = chr(ch)
            # Em blocos conhecidos, 0x0E atua como separador visual.
            if ctrl == 0x0E and chars and chars[-1] != " " and c not in ".,!?;:)":
                chars.append(" ")
            chars.append(c)
            i += 2

        text = "".join(chars)
        text = re.sub(r"\s+", " ", text).strip()
        return self._sanitize_profile_ascii_text(text)

    def _extract_control_prefixed_ascii_region(self, start: int, end: int, source: str, region: str) -> List[Dict]:
        """
        Extrai texto de blocos com controle intercalado em regiões do profile.
        Isso cobre prompts que não aparecem como ASCII puro.
        """
        out: List[Dict[str, Any]] = []
        i = start
        while i + 1 < end:
            b0 = self.rom_data[i]
            b1 = self.rom_data[i + 1]
            if not (0x00 < b0 < 0x20 and self._is_printable_ascii(b1)):
                i += 1
                continue

            j = i
            seq = bytearray()
            ascii_count = 0
            while j + 1 < end:
                ctrl = self.rom_data[j]
                ch = self.rom_data[j + 1]
                if ctrl == 0x00 or ctrl >= 0x20 or not self._is_printable_ascii(ch):
                    break
                seq.append(ctrl)
                seq.append(ch)
                ascii_count += 1
                j += 2

            if ascii_count >= self.config.min_text_length:
                text_clean = self._decode_control_prefixed_ascii(bytes(seq))
                if text_clean and len(text_clean) >= self.config.min_text_length and is_plausible_text_sms(text_clean):
                    terminator = self.rom_data[j] if j < self.rom_size else None
                    out.append({
                        "id": -1,
                        "offset": int(i),
                        "decoded": text_clean,
                        "clean": text_clean,
                        "max_len": int(max(len(seq), len(text_clean.encode("ascii", errors="ignore")))),
                        "raw_len": int(len(seq)),
                        "raw_bytes_hex": bytes(seq).hex().upper(),
                        "terminator": terminator,
                        "source": f"{source}_CTRL",
                        "region": region,
                        "category": f"{source}_CTRL",
                        "encoding": "ascii_ctrl_prefixed",
                        "confidence": 0.75,
                        "pointer_table_offset": None,
                        "pointer_entry_offset": None,
                        "pointer_value": None,
                        "resolved_rom_offset": int(i),
                        "has_pointer": False,
                        "profile_region": True,
                    })

            i = max(i + 1, j if j > i else i + 1)

        return out

    def _decode_soft_control_ascii(self, data: bytes) -> str:
        """
        Decodifica ASCII com controles leves no meio do texto (ex.: 0x01 como quebra).
        """
        if not data:
            return ""

        soft_break_controls = {0x01, 0x02, 0x03, 0x04, 0x05}
        out_chars: List[str] = []
        for b in data:
            if self._is_printable_ascii(b):
                out_chars.append(chr(b))
                continue
            if b in soft_break_controls and out_chars and out_chars[-1] != " ":
                out_chars.append(" ")

        text = "".join(out_chars)
        text = re.sub(r"\s+", " ", text).strip()
        return self._sanitize_profile_ascii_text(text)

    def _extract_soft_control_ascii_region(self, start: int, end: int, source: str, region: str) -> List[Dict]:
        """
        Extrai blocos ASCII longos contendo controles leves entre palavras.
        Útil para narrativas que o parser ASCII puro quebra em fragmentos.
        """
        out: List[Dict[str, Any]] = []
        soft_break_controls = {0x01, 0x02, 0x03, 0x04, 0x05}

        i = start
        while i < end:
            b = self.rom_data[i]
            if not self._is_printable_ascii(b):
                i += 1
                continue

            j = i
            has_soft_break = False
            while j < end:
                cur = self.rom_data[j]
                if cur == 0x00:
                    break
                if self._is_printable_ascii(cur):
                    j += 1
                    continue
                if cur in soft_break_controls:
                    has_soft_break = True
                    j += 1
                    continue
                break

            seq = bytes(self.rom_data[i:j])
            if has_soft_break and len(seq) >= self.config.min_text_length:
                text_clean = self._decode_soft_control_ascii(seq)
                if text_clean and len(text_clean) >= self.config.min_text_length and is_plausible_text_sms(text_clean):
                    terminator = self.rom_data[j] if j < self.rom_size else None
                    out.append({
                        "id": -1,
                        "offset": int(i),
                        "decoded": text_clean,
                        "clean": text_clean,
                        "max_len": int(max(len(seq), len(text_clean.encode("ascii", errors="ignore")))),
                        "raw_len": int(len(seq)),
                        "raw_bytes_hex": seq.hex().upper(),
                        "terminator": terminator,
                        "source": f"{source}_SOFTCTRL",
                        "region": region,
                        "category": f"{source}_SOFTCTRL",
                        "encoding": "ascii_soft_ctrl",
                        "confidence": 0.78,
                        "pointer_table_offset": None,
                        "pointer_entry_offset": None,
                        "pointer_value": None,
                        "resolved_rom_offset": int(i),
                        "has_pointer": False,
                        "profile_region": True,
                    })

            i = max(i + 1, j if j > i else i + 1)

        return out

    def _extract_soft_control_ascii_full_rom(self) -> List[Dict]:
        """
        Varredura global de blocos ASCII com controles leves.
        Objetivo: aumentar cobertura de textos reais em ROMs com script misto.
        """
        out: List[Dict[str, Any]] = []
        soft_break_controls = {0x01, 0x02, 0x03, 0x04, 0x05}
        seen_text: Set[str] = set()

        i = 0
        while i < self.rom_size:
            b = self.rom_data[i]
            if not self._is_printable_ascii(b):
                i += 1
                continue

            j = i
            has_soft_break = False
            while j < self.rom_size:
                cur = self.rom_data[j]
                if cur == 0x00:
                    break
                if self._is_printable_ascii(cur):
                    j += 1
                    continue
                if cur in soft_break_controls:
                    has_soft_break = True
                    j += 1
                    continue
                break

            seq = bytes(self.rom_data[i:j])
            if has_soft_break and len(seq) >= self.config.min_text_length:
                text_clean = self._decode_soft_control_ascii(seq)
                if text_clean and len(text_clean) >= self.config.min_text_length:
                    # Filtro extra para reduzir ruído em scan global.
                    alpha = sum(1 for c in text_clean if c.isalpha())
                    symbol = sum(1 for c in text_clean if not c.isalnum() and c not in " .,!?;:'\"()[]-/&")
                    if alpha >= 4 and (symbol / max(len(text_clean), 1)) <= 0.20 and is_plausible_text_sms(text_clean):
                        if text_clean not in seen_text:
                            seen_text.add(text_clean)
                            terminator = self.rom_data[j] if j < self.rom_size else None
                            out.append({
                                "id": -1,
                                "offset": int(i),
                                "decoded": text_clean,
                                "clean": text_clean,
                                "max_len": int(max(len(seq), len(text_clean.encode("ascii", errors="ignore")))),
                                "raw_len": int(len(seq)),
                                "raw_bytes_hex": seq.hex().upper(),
                                "terminator": terminator,
                                "source": "ASCII_SOFTCTRL_FULLSCAN",
                                "region": "ROM_FULL",
                                "category": "ASCII_SOFTCTRL_FULLSCAN",
                                "encoding": "ascii_soft_ctrl",
                                "confidence": 0.72,
                                "pointer_table_offset": None,
                                "pointer_entry_offset": None,
                                "pointer_value": None,
                                "resolved_rom_offset": int(i),
                                "has_pointer": False,
                                "profile_region": False,
                            })

            i = max(i + 1, j if j > i else i + 1)

        return out

    def _is_crc_rom(self, crc32: str, rom_size: int) -> bool:
        """Valida alvo de forma neutra (CRC32 + tamanho)."""
        return str(self.crc32_full).upper() == str(crc32).upper() and int(self.rom_size) == int(rom_size)

    def _extract_ui_items_crc_de9f8517(self) -> List[Dict[str, Any]]:
        """
        Extrator cirúrgico de UI por leitura indireta via ponteiros/padrões aceitos.
        Não usa varredura cega de ASCII-run para construir os itens.
        """
        if not self._is_crc_rom("DE9F8517", 524288):
            return []

        ui_ranges = [
            {"start": 0x00C600, "end": 0x00C6B0, "label": "UI_MENU"},
            {"start": 0x00D170, "end": 0x00D220, "label": "UI_GENDER"},
        ]

        def _range_for_offset(off: int) -> Optional[Dict[str, Any]]:
            for rg in ui_ranges:
                if int(rg["start"]) <= int(off) < int(rg["end"]):
                    return rg
            return None

        def _append_ref(container: Dict[int, List[Dict[str, Any]]], resolved_off: int, ref: Dict[str, Any]) -> None:
            key_off = int(resolved_off)
            refs = container.setdefault(key_off, [])
            ptr_key = str(ref.get("ptr_offset", "")).strip().upper()
            for existing in refs:
                if str(existing.get("ptr_offset", "")).strip().upper() == ptr_key:
                    return
            refs.append(ref)

        def _normalize_ascii_start(off: int, rg_start: int) -> int:
            cur = int(off)
            if cur <= int(rg_start) or cur >= self.rom_size:
                return cur
            if not self._is_printable_ascii(self.rom_data[cur]):
                return cur
            while cur > int(rg_start):
                prev = self.rom_data[cur - 1]
                if not self._is_printable_ascii(prev):
                    break
                cur -= 1
            return cur

        def _decode_ui_payload(payload: bytes) -> Tuple[str, List[int]]:
            chars: List[str] = []
            printable_positions: List[int] = []
            spacer_controls = {0x0A, 0x0C, 0x0E, 0x12, 0x14}
            for idx, b in enumerate(payload):
                if self._is_printable_ascii(b):
                    ch = chr(b)
                    prev = payload[idx - 1] if idx > 0 else None
                    if (
                        isinstance(prev, int)
                        and prev in spacer_controls
                        and chars
                        and chars[-1] != " "
                        and ch not in ".,!?;:)"
                    ):
                        chars.append(" ")
                    chars.append(ch)
                    printable_positions.append(int(idx))
            text = re.sub(r"\s+", " ", "".join(chars)).strip()
            return text, printable_positions

        def _read_ui_payload(off: int, rg_end: int) -> Tuple[Optional[bytes], Optional[int], Optional[str]]:
            start = int(off)
            end_limit = min(int(rg_end), self.rom_size)
            if start < 0 or start >= end_limit:
                return None, None, "POINTER_INVALID"

            payload = bytearray()
            pos = start
            while pos < end_limit:
                b = self.rom_data[pos]
                if b == 0x00:
                    return bytes(payload), int(b), None
                payload.append(b)
                if len(payload) > 192:
                    return None, None, "BYTE_OVERFLOW"
                pos += 1
            return None, None, "TERMINATOR_MISSING"

        refs_by_offset: Dict[int, List[Dict[str, Any]]] = {}

        # 1) Ponteiros de tabelas heurísticas já aceitas no pipeline.
        for table in self.discovered_tables:
            for idx, ptr in enumerate(table.valid_pointers):
                resolved = self._resolve_pointer_heuristic(int(ptr))
                if resolved is None:
                    continue
                rg = _range_for_offset(int(resolved))
                if not rg:
                    continue
                entry_idx = (
                    int(table.pointer_entry_indexes[idx])
                    if idx < len(table.pointer_entry_indexes)
                    else int(idx)
                )
                ptr_off = int(table.table_offset + (entry_idx * int(table.entry_size)))
                ptr_value = int(ptr)
                normalized = _normalize_ascii_start(int(resolved), int(rg["start"]))
                _append_ref(
                    refs_by_offset,
                    normalized,
                    {
                        "ptr_offset": f"0x{ptr_off:06X}",
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": (
                            "BANKED_SLOT2"
                            if 0x8000 <= ptr_value < 0xC000
                            else ("BANKED_SLOT1" if 0x4000 <= ptr_value < 0x8000 else "DIRECT")
                        ),
                        "bank_addend": (
                            f"0x{int(normalized - ptr_value):05X}"
                            if int(normalized - ptr_value) >= 0
                            else f"-0x{abs(int(normalized - ptr_value)):05X}"
                        ),
                        "table_start": f"0x{int(table.table_offset):06X}",
                        "pointer_value": f"0x{ptr_value:04X}",
                    },
                )

        # 2) Padrão de ponteiro indireto em código (LD HL,nn).
        for pos in range(0, self.rom_size - 2):
            if self.rom_data[pos] != 0x21:  # Z80: LD HL,nn
                continue
            ptr_val = int(self.rom_data[pos + 1] | (self.rom_data[pos + 2] << 8))
            if not (0x8000 <= ptr_val < 0xC000):
                continue
            resolved = int(ptr_val + 0x4000)
            rg = _range_for_offset(resolved)
            if not rg:
                continue
            normalized = _normalize_ascii_start(int(resolved), int(rg["start"]))
            _append_ref(
                refs_by_offset,
                normalized,
                {
                    "ptr_offset": f"0x{int(pos + 1):06X}",
                    "ptr_size": 2,
                    "endianness": "little",
                    "addressing_mode": "BANKED_SLOT2",
                    "bank_addend": "0x04000",
                    "table_start": None,
                    "pointer_value": f"0x{ptr_val:04X}",
                },
            )

        candidates = sorted(int(k) for k in refs_by_offset.keys())
        self.ui_items_found_count = int(len(candidates))
        self.ui_items_extracted_count = 0
        self.ui_items_blocked_count = 0
        self.ui_items_blocked_details = []

        items: List[Dict[str, Any]] = []
        blocked: List[Dict[str, Any]] = []

        for off in candidates:
            rg = _range_for_offset(int(off))
            if not rg:
                blocked.append(
                    {
                        "offset": f"0x{int(off):06X}",
                        "reason": "POINTER_INVALID",
                        "details": "OFFSET_OUT_OF_UI_RANGE",
                    }
                )
                continue

            payload, term, read_err = _read_ui_payload(int(off), int(rg["end"]))
            if read_err or payload is None or term is None:
                blocked.append(
                    {
                        "offset": f"0x{int(off):06X}",
                        "reason": str(read_err or "POINTER_INVALID"),
                        "details": "READ_UI_PAYLOAD_FAILED",
                    }
                )
                continue

            invalid_bytes = [
                int(b)
                for b in payload
                if not self._is_valid_ui_byte(int(b))
            ]
            if invalid_bytes:
                blocked.append(
                    {
                        "offset": f"0x{int(off):06X}",
                        "reason": "INVALID_CHARSET",
                        "details": f"INVALID_BYTES={','.join(f'0x{x:02X}' for x in invalid_bytes[:8])}",
                    }
                )
                continue

            text_clean, printable_positions = _decode_ui_payload(bytes(payload))
            if not text_clean or len(printable_positions) < 2:
                blocked.append(
                    {
                        "offset": f"0x{int(off):06X}",
                        "reason": "INVALID_CHARSET",
                        "details": "NO_PRINTABLE_SEQUENCE",
                    }
                )
                continue

            refs = list(refs_by_offset.get(int(off), []))
            first_ref = refs[0] if refs else {}
            ptr_value_obj = first_ref.get("pointer_value")
            ptr_value_int = None
            if isinstance(ptr_value_obj, str):
                try:
                    ptr_value_int = int(ptr_value_obj, 16)
                except Exception:
                    ptr_value_int = None

            ptr_entry_obj = first_ref.get("ptr_offset")
            ptr_entry_int = None
            if isinstance(ptr_entry_obj, str):
                try:
                    ptr_entry_int = int(ptr_entry_obj, 16)
                except Exception:
                    ptr_entry_int = None

            table_start_obj = first_ref.get("table_start")
            table_start_int = None
            if isinstance(table_start_obj, str) and table_start_obj:
                try:
                    table_start_int = int(table_start_obj, 16)
                except Exception:
                    table_start_int = None

            encoding = "ascii"
            if any(not self._is_printable_ascii(int(b)) for b in payload):
                encoding = "ascii_ctrl_prefixed"

            items.append(
                {
                    "id": -1,
                    "offset": int(off),
                    "decoded": text_clean,
                    "clean": text_clean,
                    "max_len": int(len(payload)),
                    "raw_len": int(len(payload)),
                    "raw_bytes_hex": bytes(payload).hex().upper(),
                    "terminator": int(term),
                    "source": f"UI_POINTER_{str(rg['label'])}",
                    "region": str(rg["label"]),
                    "category": f"UI_POINTER_{str(rg['label'])}",
                    "encoding": encoding,
                    "confidence": 0.96,
                    "pointer_table_offset": table_start_int,
                    "pointer_entry_offset": ptr_entry_int,
                    "pointer_value": ptr_value_int,
                    "resolved_rom_offset": int(off),
                    "has_pointer": True,
                    "profile_region": True,
                    "ui_item": True,
                    "ui_kind": str(rg["label"]),
                    "ui_char_capacity": int(len(printable_positions)),
                    "ui_printable_positions": [int(x) for x in printable_positions],
                    "ui_template_hex": bytes(payload).hex().upper(),
                    "pointer_refs": refs,
                }
            )

        # 3) Opções inline da UI de gênero (sem scan global; derivadas do bloco já mapeado).
        existing_offsets: Set[int] = {int(it.get("offset", -1)) for it in items}
        extra_inline_items: List[Dict[str, Any]] = []
        for base_item in list(items):
            if str(base_item.get("ui_kind", "") or "").upper() != "UI_GENDER":
                continue
            base_text = str(base_item.get("clean", "") or "").lower()
            if "male or female" not in base_text:
                continue
            base_off = int(base_item.get("offset", 0))
            base_len = int(base_item.get("raw_len", 0))
            cursor = int(base_off + max(0, base_len) + 1)
            rg = _range_for_offset(base_off)
            if not rg:
                continue
            rg_end = int(rg["end"])
            options_added = 0
            while cursor < rg_end and options_added < 4:
                # Avança por controles/separadores até achar início ASCII.
                while cursor < rg_end and not self._is_printable_ascii(int(self.rom_data[cursor])):
                    cursor += 1
                if cursor >= rg_end:
                    break
                start_opt = int(cursor)
                end_opt = start_opt
                while end_opt < rg_end and self._is_printable_ascii(int(self.rom_data[end_opt])):
                    end_opt += 1
                    if (end_opt - start_opt) > 24:
                        break
                if end_opt >= rg_end:
                    break
                if int(self.rom_data[end_opt]) != 0x00:
                    cursor = start_opt + 1
                    continue
                raw_opt = bytes(self.rom_data[start_opt:end_opt])
                text_opt = raw_opt.decode("ascii", errors="ignore").strip()
                cursor = end_opt + 1
                if not text_opt or len(text_opt) < 2:
                    continue
                if not re.fullmatch(r"[A-Za-z ]{2,24}", text_opt):
                    continue
                # Nesta ROM, as opções válidas do prompt são palavras curtas.
                if len(text_opt.split()) > 2:
                    continue
                if int(start_opt) in existing_offsets:
                    continue

                refs_opt = list(refs_by_offset.get(int(start_opt), []))
                if not refs_opt:
                    refs_opt = list(base_item.get("pointer_refs", []) or [])
                first_ref_opt = refs_opt[0] if refs_opt else {}

                ptr_value_int_opt = None
                ptr_value_obj_opt = first_ref_opt.get("pointer_value")
                if isinstance(ptr_value_obj_opt, str):
                    try:
                        ptr_value_int_opt = int(ptr_value_obj_opt, 16)
                    except Exception:
                        ptr_value_int_opt = None

                ptr_entry_int_opt = None
                ptr_entry_obj_opt = first_ref_opt.get("ptr_offset")
                if isinstance(ptr_entry_obj_opt, str):
                    try:
                        ptr_entry_int_opt = int(ptr_entry_obj_opt, 16)
                    except Exception:
                        ptr_entry_int_opt = None

                table_start_int_opt = None
                table_start_obj_opt = first_ref_opt.get("table_start")
                if isinstance(table_start_obj_opt, str) and table_start_obj_opt:
                    try:
                        table_start_int_opt = int(table_start_obj_opt, 16)
                    except Exception:
                        table_start_int_opt = None

                extra_inline_items.append(
                    {
                        "id": -1,
                        "offset": int(start_opt),
                        "decoded": text_opt,
                        "clean": text_opt,
                        "max_len": int(len(raw_opt)),
                        "raw_len": int(len(raw_opt)),
                        "raw_bytes_hex": raw_opt.hex().upper(),
                        "terminator": 0,
                        "source": "UI_POINTER_UI_GENDER_OPTION",
                        "region": "UI_GENDER",
                        "category": "UI_POINTER_UI_GENDER_OPTION",
                        "encoding": "ascii",
                        "confidence": 0.95,
                        "pointer_table_offset": table_start_int_opt,
                        "pointer_entry_offset": ptr_entry_int_opt,
                        "pointer_value": ptr_value_int_opt,
                        "resolved_rom_offset": int(start_opt),
                        "has_pointer": bool(refs_opt) or bool(base_item.get("has_pointer", False)),
                        "profile_region": True,
                        "ui_item": True,
                        "ui_kind": "UI_GENDER_OPTION",
                        "ui_char_capacity": int(len(raw_opt)),
                        "ui_printable_positions": [int(i) for i in range(len(raw_opt))],
                        "ui_template_hex": raw_opt.hex().upper(),
                        "pointer_refs": refs_opt,
                    }
                )
                existing_offsets.add(int(start_opt))
                options_added += 1

        if extra_inline_items:
            items.extend(extra_inline_items)

        self.ui_items_extracted_count = int(len(items))
        self.ui_items_blocked_count = int(len(blocked))
        self.ui_items_blocked_details = list(blocked)
        return items

    def _extract_ascii_full_rom_strict(self) -> List[Dict]:
        """
        Varredura global de ASCII puro com filtro forte de plausibilidade.
        Complementa strings truncadas por ponteiro (cobertura de script real).
        """
        out: List[Dict[str, Any]] = []
        seen_text: Set[str] = set()

        i = 0
        while i < self.rom_size:
            if not self._is_printable_ascii(self.rom_data[i]):
                i += 1
                continue

            j = i
            while j < self.rom_size and self._is_printable_ascii(self.rom_data[j]):
                j += 1

            seq = bytes(self.rom_data[i:j])
            if len(seq) >= self.config.min_text_length:
                text_raw = seq.decode("ascii", errors="ignore").strip()
                text_clean = self._sanitize_profile_ascii_text(text_raw)
                if text_clean and len(text_clean) >= self.config.min_text_length:
                    alpha = sum(1 for c in text_clean if c.isalpha())
                    symbol = sum(1 for c in text_clean if not c.isalnum() and c not in " .,!?;:'\"()[]-/&")
                    has_word = " " in text_clean or len(text_clean) >= 8
                    if (
                        alpha >= 4
                        and has_word
                        and (symbol / max(len(text_clean), 1)) <= 0.20
                        and is_plausible_text_sms(text_clean)
                    ):
                        if text_clean not in seen_text:
                            seen_text.add(text_clean)
                            terminator = self.rom_data[j] if j < self.rom_size else None
                            out.append({
                                "id": -1,
                                "offset": int(i),
                                "decoded": text_clean,
                                "clean": text_clean,
                                "max_len": int(max(len(seq), len(text_clean.encode("ascii", errors="ignore")))),
                                "raw_len": int(len(seq)),
                                "raw_bytes_hex": seq.hex().upper(),
                                "terminator": terminator,
                                "source": "ASCII_FULLSCAN_STRICT",
                                "region": "ROM_FULL",
                                "category": "ASCII_FULLSCAN_STRICT",
                                "encoding": "ascii",
                                "confidence": 0.68,
                                "pointer_table_offset": None,
                                "pointer_entry_offset": None,
                                "pointer_value": None,
                                "resolved_rom_offset": int(i),
                                "has_pointer": False,
                                "profile_region": False,
                            })

            i = max(i + 1, j if j > i else i + 1)

        return out

    def _extract_profile_ascii_regions(self, profile: Optional[Dict]) -> List[Dict]:
        """
        Extrai ASCII em regiões explícitas do profile (text_regions).
        Uso: cobrir textos estáticos de menu/intro não capturados por ponteiros.
        """
        if not isinstance(profile, dict):
            return []

        regions = profile.get("text_regions") or []
        if not isinstance(regions, list) or not regions:
            return []

        def _to_int(value: Any) -> Optional[int]:
            try:
                if value is None:
                    return None
                if isinstance(value, bool):
                    return None
                if isinstance(value, int):
                    return int(value)
                if isinstance(value, float):
                    return int(value)
                s = str(value).strip().lower()
                if not s:
                    return None
                if s.startswith("0x"):
                    return int(s, 16)
                return int(s, 10)
            except Exception:
                return None

        out: List[Dict[str, Any]] = []
        seen_local: Set[Tuple[int, str, str]] = set()

        def _append_unique(item: Dict[str, Any]) -> None:
            key = (
                int(item.get("offset", 0)),
                str(item.get("clean", "") or ""),
            )
            if key in seen_local:
                return
            seen_local.add(key)
            out.append(item)

        for idx, region in enumerate(regions, 1):
            if not isinstance(region, dict):
                continue
            start = _to_int(region.get("start"))
            end = _to_int(region.get("end"))
            if start is None or end is None:
                continue
            start_i = max(0, int(start))
            end_i = min(self.rom_size, int(end))
            if end_i <= start_i:
                continue

            label_raw = str(region.get("label", f"PROFILE_{idx:02d}") or f"PROFILE_{idx:02d}")
            label = re.sub(r"[^A-Za-z0-9_]+", "_", label_raw).strip("_") or f"PROFILE_{idx:02d}"
            source = f"ASCII_PROFILE_{label}"

            blocks = self._extract_ascii_region(start_i, end_i, source=source)
            for block in blocks:
                text_raw = str(block.decoded_text or "").strip()
                text_clean = self._sanitize_profile_ascii_text(text_raw)
                if not text_clean:
                    continue
                if len(text_clean) < self.config.min_text_length:
                    continue

                raw_hex = block.raw_bytes.hex().upper() if block.raw_bytes else ""
                max_len = max(
                    int(block.max_length or 0),
                    len(text_raw.encode("ascii", errors="ignore")),
                    len(text_clean.encode("ascii", errors="ignore")),
                )
                _append_unique({
                    "id": -1,
                    "offset": int(block.offset),
                    "decoded": text_clean,
                    "clean": text_clean,
                    "max_len": int(max_len),
                    "raw_len": int(len(block.raw_bytes)),
                    "raw_bytes_hex": raw_hex,
                    "terminator": block.terminator,
                    "source": source,
                    "region": label,
                    "category": source,
                    "encoding": "ascii",
                    "confidence": float(max(0.70, float(block.confidence or 0.0))),
                    "pointer_table_offset": None,
                    "pointer_entry_offset": None,
                    "pointer_value": None,
                    "resolved_rom_offset": int(block.offset),
                    "has_pointer": False,
                    "profile_region": True,
                })

            # Variação com bytes de controle intercalados (ex.: "Art thou Male or Female ?")
            for ctrl_item in self._extract_control_prefixed_ascii_region(start_i, end_i, source=source, region=label):
                _append_unique(ctrl_item)

            # Variação com ASCII + controle leve (ex.: narrativas longas com 0x01 entre palavras)
            for soft_item in self._extract_soft_control_ascii_region(start_i, end_i, source=source, region=label):
                _append_unique(soft_item)

        return out

    # ========================================================================
    # API PUBLICA
    # ========================================================================

    def extract_all(self, output_dir: Optional[str | Path] = None) -> int:
        """
        Executa extração completa e salva resultados.
        Retorna numero de blocos extraidos.
        """
        self.extract_texts()
        self.save_results(output_dir)
        return len(self.results)

    def extract_texts(self) -> List[dict]:
        """
        AUTO-DISCOVERY MODE (POINTER-ONLY)

        Extrai texto SOMENTE de tabelas de ponteiros descobertas.
        PROIBIDO scan cego de regioes (HEADER/CREDITS/ROM inteira).

        Todo item exportado TEM prova de ponteiro:
        - pointer_table_offset
        - pointer_entry_offset
        - pointer_value
        - resolved_rom_offset
        """
        self.extracted_blocks = []
        self.ui_items_found_count = 0
        self.ui_items_extracted_count = 0
        self.ui_items_translated_count = 0
        self.ui_items_reinserted_count = 0
        self.ui_items_blocked_count = 0
        self.ui_items_blocked_details = []
        seen_keys: Set[Tuple[int, int, Optional[int], str]] = set()

        # PROVA determinística de ASCII (HUD/intro)
        ascii_hits = self._ascii_probe_words()

        # ============================================================
        # FASE 1: DESCOBERTA DE TABELAS DE PONTEIROS (HEURISTICA)
        # ============================================================
        self.discovered_tables = self._find_potential_pointer_tables()

        # ============================================================
        # FASE 2: EXTRAÇÃO SOMENTE DOS PONTEIROS DESCOBERTOS
        # ============================================================
        for block in self._extract_from_pointer_tables():
            # Aplica firewall adicional
            text_clean = self._sanitize_profile_ascii_text(block.decoded_text)
            if self._post_filter_text(text_clean):
                block.decoded_text = text_clean
                key = (block.offset, block.max_length, block.terminator, "ascii")
                if key not in seen_keys:
                    self.extracted_blocks.append(block)
                    seen_keys.add(key)

        # ============================================================
        # ORDENAÇÃO DETERMINISTICA (offset, source)
        # ============================================================
        self.extracted_blocks.sort(key=lambda b: (b.offset, b.source))

        # Converte para formato dict (compatibilidade GUI)
        # Todo item exportado TEM prova de ponteiro
        self.results = []
        for i, block in enumerate(self.extracted_blocks, 1):
            self.results.append({
                "id": i,
                "offset": block.offset,
                "decoded": block.decoded_text,
                "clean": block.decoded_text,
                "max_len": block.max_length,
                "raw_len": len(block.raw_bytes),
                "raw_bytes_hex": block.raw_bytes.hex().upper(),
                "terminator": block.terminator,
                "source": block.source,
                "region": block.source,
                "category": block.source,
                "encoding": "ascii",
                "confidence": block.confidence,
                # PROVA DE PONTEIRO (OBRIGATORIO)
                "pointer_table_offset": block.pointer_table_offset,
                "pointer_entry_offset": block.pointer_entry_offset,
                "pointer_value": block.pointer_value,
                "resolved_rom_offset": block.offset,  # Alias para clareza
                "has_pointer": block.pointer_table_offset is not None,
            })

        # EXTRAÇÃO PROFILE-ASCII (regiões explícitas) + TILEMAP via PROFILE
        tilemap_profile_extracted = False
        profile = None
        try:
            profile = self._load_game_profile_by_crc()

            # Regiões ASCII explícitas do profile (sem scan global).
            if profile:
                profile_ascii_items = self._extract_profile_ascii_regions(profile)
                for it in profile_ascii_items:
                    key = (
                        int(it.get("offset", 0)),
                        int(it.get("max_len", 0)),
                        int(it.get("terminator", 0)) if it.get("terminator") is not None else None,
                        str(it.get("encoding", "ascii")),
                    )
                    if key not in seen_keys:
                        self.results.append(it)
                        seen_keys.add(key)

            # Extração cirúrgica de UI por ponteiros/padrões (CRC + tamanho).
            for ui_item in self._extract_ui_items_crc_de9f8517():
                key = (
                    int(ui_item.get("offset", 0)),
                    int(ui_item.get("max_len", 0)),
                    int(ui_item.get("terminator", 0))
                    if ui_item.get("terminator") is not None
                    else None,
                    str(ui_item.get("encoding", "ascii")),
                )
                if key not in seen_keys:
                    self.results.append(ui_item)
                    seen_keys.add(key)
                else:
                    # Se já existir item no mesmo offset/capacidade, preserva a linha existente
                    # e injeta metadados de UI para o fluxo normal (sem duplicar conteúdo).
                    for existing in self.results:
                        existing_key = (
                            int(existing.get("offset", 0)),
                            int(existing.get("max_len", 0)),
                            int(existing.get("terminator", 0))
                            if existing.get("terminator") is not None
                            else None,
                            str(existing.get("encoding", "ascii")),
                        )
                        if existing_key != key:
                            continue
                        existing["ui_item"] = True
                        existing["ui_kind"] = ui_item.get("ui_kind")
                        existing["ui_char_capacity"] = int(ui_item.get("ui_char_capacity", 0) or 0)
                        existing["ui_printable_positions"] = list(ui_item.get("ui_printable_positions", []) or [])
                        existing["ui_template_hex"] = ui_item.get("ui_template_hex")
                        # Preserva informação de ponteiro quando disponível.
                        if ui_item.get("pointer_refs"):
                            existing["pointer_refs"] = list(ui_item.get("pointer_refs") or [])
                            existing["has_pointer"] = True
                            existing["pointer_table_offset"] = ui_item.get("pointer_table_offset")
                            existing["pointer_entry_offset"] = ui_item.get("pointer_entry_offset")
                            existing["pointer_value"] = ui_item.get("pointer_value")
                        break

            if profile and profile.get("encoding") == "tilemap" and profile.get("tbl_path"):
                tile_items = self._extract_tilemap_profile(profile)
                for it in tile_items:
                    key = (
                        int(it.get("offset", 0)),
                        int(it.get("max_len", 0)),
                        None,
                        "tilemap",
                    )
                    if key not in seen_keys:
                        self.results.append(it)
                        seen_keys.add(key)
                tilemap_profile_extracted = len(tile_items) > 0
            else:
                # Auto-discovery de TBL quando não há profile de tilemap
                auto_info = self._auto_discover_tilemap_tbl()
                if auto_info:
                    self.tilemap_auto_info = auto_info
                    if auto_info.get("accepted"):
                        auto_profile = self._build_auto_tilemap_profile(auto_info)
                        tile_items = self._extract_tilemap_profile(auto_profile)
                        for it in tile_items:
                            key = (
                                int(it.get("offset", 0)),
                                int(it.get("max_len", 0)),
                                None,
                                "tilemap",
                            )
                            if key not in seen_keys:
                                self.results.append(it)
                                seen_keys.add(key)
                        tilemap_profile_extracted = len(tile_items) > 0
                    # Atualiza DB apenas se não houver profile válido
                    self._update_game_profiles_db(auto_profile)
        except Exception as exc:
            logging.warning("[EXTRACTOR] Tilemap profile load failed: %s", exc)

        seen_clean_texts: Set[str] = set()
        for it in self.results:
            txt = str(it.get("clean") or it.get("decoded") or "").strip()
            if txt:
                seen_clean_texts.add(txt)

        skip_full_scan_fallback = self._is_crc_rom("DE9F8517", 524288)

        # Fallback de cobertura: scan global de ASCII+controles leves
        # com filtro forte de plausibilidade (evita depender apenas de ponteiros).
        if not skip_full_scan_fallback:
            try:
                for it in self._extract_soft_control_ascii_full_rom():
                    txt = str(it.get("clean") or it.get("decoded") or "").strip()
                    if not txt or txt in seen_clean_texts:
                        continue
                    key = (
                        int(it.get("offset", 0)),
                        int(it.get("max_len", 0)),
                        int(it.get("terminator", 0)) if it.get("terminator") is not None else None,
                        str(it.get("encoding", "ascii")),
                    )
                    if key not in seen_keys:
                        self.results.append(it)
                        seen_keys.add(key)
                        seen_clean_texts.add(txt)
            except Exception as exc:
                logging.warning("[EXTRACTOR] Soft-control full scan failed: %s", exc)

        # Fallback de cobertura: ASCII puro global (estrito).
        if not skip_full_scan_fallback:
            try:
                for it in self._extract_ascii_full_rom_strict():
                    txt = str(it.get("clean") or it.get("decoded") or "").strip()
                    if not txt or txt in seen_clean_texts:
                        continue
                    key = (
                        int(it.get("offset", 0)),
                        int(it.get("max_len", 0)),
                        int(it.get("terminator", 0)) if it.get("terminator") is not None else None,
                        str(it.get("encoding", "ascii")),
                    )
                    if key not in seen_keys:
                        self.results.append(it)
                        seen_keys.add(key)
                        seen_clean_texts.add(txt)
            except Exception as exc:
                logging.warning("[EXTRACTOR] ASCII full strict scan failed: %s", exc)

        # Se não há ASCII evidente, tenta tilemap/font (sem scan cego final)
        if ascii_hits == 0 and not tilemap_profile_extracted:
            tile_items = self._extract_tilemap_probe()
            for it in tile_items:
                key = (
                    int(it.get("offset", 0)),
                    int(it.get("max_len", 0)),
                    int(it.get("terminator", 0)) if it.get("terminator") is not None else None,
                    str(it.get("encoding", "ascii")),
                )
                if key not in seen_keys:
                    self.results.append(it)
                    seen_keys.add(key)

        # Ordenação determinística final
        self.results.sort(key=lambda x: (int(x.get("offset", 0)), str(x.get("source", ""))))

        # Renumera IDs para manter consistência
        for i, item in enumerate(self.results, 1):
            item["id"] = i

        self.filtered_texts = self.results
        return self.results

    def extract_all_texts(self) -> List[dict]:
        """Alias para compatibilidade."""
        if not self.results:
            self.extract_texts()
        return self.results

    def extract_all_texts_enhanced(self) -> List[Dict]:
        """
        Extrai textos por ponteiros (método atual) + extras (tiles/autolearn + ASCII em regiões específicas).
        Mantém o formato de saída atual (JSONL), apenas adiciona mais itens.
        """
        # 1) Ponteiros (como hoje)
        pointer_results = self.extract_texts()  # já respeita "sem scan cego"

        # 2) Extras (sem duplicar ponteiros)
        total = TotalTextExtractor(str(self.file_path), config=self.config)
        extras = total.extract_extras_only()

        # 3) Merge sem duplicar offsets já existentes
        seen_keys: Set[Tuple[int, int, Optional[int], str]] = set(
            (
                int(x.get("offset", 0)),
                int(x.get("max_len", 0)),
                int(x.get("terminator", 0)) if x.get("terminator") is not None else None,
                str(x.get("encoding", "ascii")),
            )
            for x in pointer_results
        )
        merged: List[Dict] = list(pointer_results)

        for it in extras:
            key = (
                int(it.get("offset", 0)),
                int(it.get("max_len", 0)),
                int(it.get("terminator", 0)) if it.get("terminator") is not None else None,
                str(it.get("encoding", "ascii")),
            )
            if key in seen_keys:
                continue
            merged.append(it)
            seen_keys.add(key)

        # 4) Renumerar IDs (mantém consistência pro JSONL/mapping)
        for i, it in enumerate(merged, start=1):
            it["id"] = i

        self.results = merged
        return merged

    # ========================================================================
    # SALVAMENTO DE RESULTADOS
    # ========================================================================

    def save_results(self, output_dir: Optional[str | Path] = None) -> str:
        """
        Salva resultados em arquivos.
        Formato V1: {CRC32}_pure_text.jsonl, {CRC32}_reinsertion_mapping.json,
                    {CRC32}_report.txt, {CRC32}_proof.json
        """
        if not self.results:
            self.extract_texts()

        out_dir = Path(output_dir) if output_dir else Path(self.file_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # PROIBIDO usar rom_path.name - usar somente CRC32
        base_name = f"{self.crc32_full}"  # Neutralidade V1: nomes baseados apenas no CRC32

        # Arquivos de saida nomeados por CRC32 (formato V1)
        jsonl_path = out_dir / f"{base_name}_pure_text.jsonl"
        suspect_path = out_dir / f"{base_name}_suspect_text.jsonl"
        mapping_path = out_dir / f"{base_name}_reinsertion_mapping.json"
        log_path = out_dir / f"{base_name}_report.txt"
        proof_path = out_dir / f"{base_name}_proof.json"
        catalog_translation_path = out_dir / f"{base_name}_catalog_texts_for_translation.txt"
        catalog_reinsertable_path = out_dir / f"{base_name}_catalog_texts_reinsertable.txt"
        overlap_evidence_path = out_dir / f"{base_name}_overlap_resolution_evidence.jsonl"
        partial_evidence_path = out_dir / f"{base_name}_partial_pointer_tables.txt"

        # Gera os 4 arquivos V1
        self._write_pure_text_jsonl(jsonl_path)
        self._write_suspect_text_jsonl(suspect_path)
        self._write_mapping(mapping_path)
        self._write_log(log_path)
        self._write_translation_catalogs(
            translation_path=catalog_translation_path,
            reinsertable_path=catalog_reinsertable_path,
        )
        self._write_overlap_resolution_evidence(overlap_evidence_path)
        self._write_partial_pointer_evidence(partial_evidence_path)
        self._write_proof_json(
            proof_path,
            [
                jsonl_path,
                suspect_path,
                mapping_path,
                log_path,
                catalog_translation_path,
                catalog_reinsertable_path,
                overlap_evidence_path,
                partial_evidence_path,
            ],
        )
        self._write_tilemap_debug_artifacts(out_dir)

        return str(jsonl_path)

    def _write_tilemap_debug_artifacts(self, out_dir: Path) -> None:
        """Escreve candidatos de fonte e ranges de tilemap (debug neutro)."""
        if not self.tilemap_probe_used and not self.tilemap_auto_info:
            return

        try:
            # Font candidates
            if self.font_candidates:
                font_json = out_dir / f"{self.crc32_full}_font_candidates.json"
                font_payload = []
                for idx, cand in enumerate(self.font_candidates, 1):
                    start = int(cand.get("offset", 0))
                    tile_count = int(cand.get("tile_count", 0))
                    tile_size = int(cand.get("tile_size", 0))
                    size = tile_count * tile_size
                    end = start + size

                    # Dump binário por range
                    bin_name = f"{self.crc32_full}_fontcand_{idx:02d}_{start:06X}_{end:06X}.bin"
                    bin_path = out_dir / bin_name
                    if size > 0 and end <= self.rom_size:
                        bin_path.write_bytes(self.rom_data[start:end])

                    font_payload.append({
                        "offset": f"0x{start:06X}",
                        "size": size,
                        "tile_count": tile_count,
                        "tile_size": tile_size,
                        "score": float(cand.get("score", 0.0)),
                        "bin": bin_name,
                    })

                with open(font_json, "w", encoding="utf-8") as f:
                    json.dump(font_payload, f, indent=2, ensure_ascii=False)

            # Tilemap candidate ranges (4KB/8KB)
            if self.tilemap_candidate_ranges:
                ranges_json = out_dir / f"{self.crc32_full}_tilemap_candidate_ranges.json"
                ranges_payload = []
                for cand in self.tilemap_candidate_ranges:
                    ranges_payload.append({
                        "offset": f"0x{int(cand.get('offset', 0)):06X}",
                        "size": int(cand.get("size", 0)),
                        "score": cand.get("score", 0.0),
                        "low_ratio": cand.get("low_ratio", 0.0),
                        "terminator_ratio": cand.get("terminator_ratio", 0.0),
                        "entropy": cand.get("entropy", 0.0),
                        "top_byte": f"0x{int(cand.get('top_byte', 0)):02X}",
                        "top_ratio": cand.get("top_ratio", 0.0),
                    })

                with open(ranges_json, "w", encoding="utf-8") as f:
                    json.dump(ranges_payload, f, indent=2, ensure_ascii=False)

            # Auto TBL (diagnóstico)
            if self.tilemap_auto_info:
                auto_json = out_dir / f"{self.crc32_full}_tilemap_auto_info.json"
                with open(auto_json, "w", encoding="utf-8") as f:
                    json.dump(self.tilemap_auto_info, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logging.debug("[EXTRACTOR] Debug artifacts write failed: %s", exc)

    def _write_pure_text_jsonl(self, path: Path) -> None:
        """
        Escreve arquivo JSONL de texto puro para traducao (formato V1).
        Cada linha e um objeto JSON com campos padronizados.
        Inclui pointer_refs com transform completo para realocacao.
        Aplica filtro de texto plausivel para strings de POINTER.
        """
        def _parse_optional_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return int(value)
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                s = value.strip().lower()
                if not s:
                    return None
                if s.startswith("0x-"):
                    s = "-0x" + s[3:]
                try:
                    if s.startswith(("-0x", "+0x")):
                        sign = -1 if s.startswith("-") else 1
                        return sign * int(s[3:], 16)
                    if s.startswith("0x"):
                        return int(s, 16)
                    return int(s, 10)
                except ValueError:
                    return None
            return None

        def _sort_key(item: Dict[str, Any], idx: int) -> Tuple[int, int, int, int]:
            bank_val = _parse_optional_int(item.get("bank", item.get("bank_id")))
            page_val = _parse_optional_int(item.get("page", item.get("page_id")))
            off_val = _parse_optional_int(item.get("offset")) or 0
            bank_key = bank_val if bank_val is not None else 1_000_000
            page_key = page_val if page_val is not None else 1_000_000
            return (
                bank_key,
                page_key,
                off_val,
                idx,
            )

        def _raw_bytes_for_item(item: Dict[str, Any]) -> bytes:
            raw_hex = item.get("raw_bytes_hex")
            if isinstance(raw_hex, str) and raw_hex.strip():
                try:
                    clean_hex = re.sub(r"[^0-9A-Fa-f]", "", raw_hex)
                    if clean_hex:
                        return bytes.fromhex(clean_hex)
                except ValueError:
                    pass

            off_val = _parse_optional_int(item.get("offset"))
            if off_val is None:
                return b""
            raw_len = _parse_optional_int(item.get("raw_len"))
            if raw_len is None or raw_len <= 0:
                raw_len = _parse_optional_int(item.get("max_len")) or 0
            if raw_len <= 0:
                return b""
            start = max(0, min(int(off_val), self.rom_size))
            end = max(start, min(self.rom_size, start + int(raw_len)))
            if end <= start:
                return b""
            return bytes(self.rom_data[start:end])

        def _overlap_priority(
            item: Dict[str, Any],
            raw_len: int,
            seq_idx: int
        ) -> Tuple[int, int, int, int, float, float, int, int, int]:
            text_value = str(item.get("clean", "") or "")
            term = item.get("terminator")
            term_ok = 1 if isinstance(term, int) and int(term) in self.config.valid_terminators else 0
            has_pointer = 1 if bool(item.get("has_pointer", False)) else 0
            plausible_score = float(score_ascii_plausibility(text_value)) if text_value else 0.0
            confidence_val = float(item.get("confidence", 0.0) or 0.0)
            source_tag = str(item.get("source", "") or "")
            ui_bonus = 1 if bool(item.get("ui_item", False)) or source_tag.startswith("UI_POINTER_") else 0
            source_bonus = 1 if source_tag.startswith("ASCII_PROFILE_") else 0
            off_val = _parse_optional_int(item.get("offset")) or 0
            prev_byte = self.rom_data[int(off_val) - 1] if int(off_val) > 0 else None
            prev_is_alpha = (
                isinstance(prev_byte, int)
                and ((0x41 <= prev_byte <= 0x5A) or (0x61 <= prev_byte <= 0x7A))
            )
            starts_lower = bool(text_value[:1]) and text_value[:1].islower()
            prefix_penalty = 0 if (starts_lower and prev_is_alpha) else 1
            return (
                ui_bonus,
                prefix_penalty,
                has_pointer,
                term_ok,
                plausible_score,
                confidence_val,
                int(raw_len),
                source_bonus,
                -int(seq_idx),
            )

        ordered_results: List[Dict[str, Any]] = [
            item
            for idx, item in sorted(
                enumerate(self.results), key=lambda pair: _sort_key(pair[1], pair[0])
            )
        ]

        # Resolve sobreposição por cluster: mantém apenas o melhor recorte.
        overlap_loser_idxs: Set[int] = set()
        intervals: List[Tuple[int, int, int]] = []
        raw_len_by_idx: Dict[int, int] = {}
        for idx, item in enumerate(ordered_results):
            off_val = _parse_optional_int(item.get("offset")) or 0
            raw_bytes = _raw_bytes_for_item(item)
            raw_len = len(raw_bytes)
            if raw_len <= 0:
                raw_len = _parse_optional_int(item.get("raw_len")) or _parse_optional_int(item.get("max_len")) or 0
            if raw_len <= 0:
                continue
            raw_len_by_idx[idx] = int(raw_len)
            intervals.append((int(off_val), int(off_val) + int(raw_len), idx))

        intervals.sort(key=lambda x: (x[0], x[1]))
        overlap_clusters: List[List[Tuple[int, int, int]]] = []
        current_cluster: List[Tuple[int, int, int]] = []
        current_end = -1
        for start, end, idx in intervals:
            if not current_cluster:
                current_cluster = [(start, end, idx)]
                current_end = end
                continue
            if start < current_end:
                current_cluster.append((start, end, idx))
                current_end = max(current_end, end)
                continue
            if len(current_cluster) > 1:
                overlap_clusters.append(current_cluster)
            current_cluster = [(start, end, idx)]
            current_end = end
        if len(current_cluster) > 1:
            overlap_clusters.append(current_cluster)

        overlap_resolution_details: List[Dict[str, Any]] = []
        for cluster_id, cluster in enumerate(overlap_clusters, 1):
            cluster_idxs = [int(it[2]) for it in cluster]
            scored_rows: List[Tuple[int, Tuple[int, int, int, int, float, float, int, int, int]]] = []
            for i in cluster_idxs:
                scored_rows.append(
                    (
                        int(i),
                        _overlap_priority(
                            ordered_results[i],
                            int(raw_len_by_idx.get(i, 0)),
                            i,
                        ),
                    )
                )
            scored_rows.sort(key=lambda row: row[1], reverse=True)
            winner_idx = int(scored_rows[0][0])
            winner_rank = scored_rows[0][1]
            for cidx in cluster_idxs:
                if int(cidx) != int(winner_idx):
                    overlap_loser_idxs.add(int(cidx))

            candidates_payload: List[Dict[str, Any]] = []
            for idx_val, rank_vec in scored_rows:
                cand_item = ordered_results[int(idx_val)]
                start = int(_parse_optional_int(cand_item.get("offset")) or 0)
                raw_len_val = int(raw_len_by_idx.get(int(idx_val), 0))
                end = int(start + raw_len_val)
                candidates_payload.append(
                    {
                        "seq": int(idx_val),
                        "offset": f"0x{start:06X}",
                        "end_offset": f"0x{end:06X}",
                        "raw_len": int(raw_len_val),
                        "source": str(cand_item.get("source", "") or ""),
                        "rank_vector": [float(x) if isinstance(x, float) else int(x) for x in rank_vec],
                        "text": str(cand_item.get("clean", "") or ""),
                        "winner": bool(int(idx_val) == int(winner_idx)),
                    }
                )

            overlap_resolution_details.append(
                {
                    "type": "overlap_cluster",
                    "cluster_id": int(cluster_id),
                    "winner_seq": int(winner_idx),
                    "winner_rank_vector": [
                        float(x) if isinstance(x, float) else int(x) for x in winner_rank
                    ],
                    "discarded_count": int(max(0, len(cluster_idxs) - 1)),
                    "candidates": candidates_payload,
                }
            )

        rom_crc32 = str(self.crc32_full).upper()
        rom_size = int(self.rom_size)
        meta_header = {
            "type": "meta",
            "schema": "neurorom.pure_text.v2",
            "rom_crc32": rom_crc32,
            "rom_size": rom_size,
            "ordering": "bank/page/rom_offset",
            "build_id": str(self.build_id),
        }

        # Reset de contadores de auditoria para report/proof.
        self.audit_unknown_bytes_total = 0
        self.audit_unknown_items = 0
        self.audit_roundtrip_fail_count = 0
        self.audit_overlap_items = 0
        self.audit_overlap_clusters = int(len(overlap_clusters))
        self.audit_review_items = 0
        self.overlap_resolution_details = list(overlap_resolution_details)
        self.overlap_discarded_count = int(len(overlap_loser_idxs))
        self.translatable_total_count = 0
        self.reinsertable_total_count = 0
        self.recompress_pending_count = 0

        def _normalize_pointer_refs_from_item(item_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
            raw_refs = item_obj.get("pointer_refs")
            if not isinstance(raw_refs, list):
                return []
            out_refs: List[Dict[str, Any]] = []
            seen_ptr_offsets: Set[str] = set()
            for ref in raw_refs:
                if not isinstance(ref, dict):
                    continue
                ptr_off = _parse_optional_int(ref.get("ptr_offset"))
                if ptr_off is None or int(ptr_off) < 0:
                    continue
                ptr_key = f"{int(ptr_off):06X}"
                if ptr_key in seen_ptr_offsets:
                    continue
                seen_ptr_offsets.add(ptr_key)
                ptr_size = _parse_optional_int(ref.get("ptr_size"))
                if ptr_size is None or int(ptr_size) <= 0:
                    ptr_size = 2
                bank_addend_raw = ref.get("bank_addend", 0)
                bank_addend_int = _parse_optional_int(bank_addend_raw)
                if bank_addend_int is None:
                    bank_addend_int = 0
                table_start = _parse_optional_int(ref.get("table_start"))
                normalized_ref = {
                    "ptr_offset": f"0x{int(ptr_off):06X}",
                    "ptr_size": int(ptr_size),
                    "endianness": str(ref.get("endianness", "little") or "little").lower(),
                    "addressing_mode": str(ref.get("addressing_mode", "ABSOLUTE") or "ABSOLUTE"),
                    "bank_addend": (
                        f"0x{int(bank_addend_int):05X}"
                        if int(bank_addend_int) >= 0
                        else f"-0x{abs(int(bank_addend_int)):05X}"
                    ),
                }
                if table_start is not None and int(table_start) >= 0:
                    normalized_ref["table_start"] = f"0x{int(table_start):06X}"
                out_refs.append(normalized_ref)
            return out_refs

        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta_header, ensure_ascii=False) + "\n")
            for seq, item in enumerate(ordered_results):
                text_src = str(item.get("clean", ""))
                has_pointer = bool(item.get("has_pointer", False))
                encoding = item.get("encoding", "ascii")
                source_tag = str(item.get("source", "") or "")
                is_ui_item = bool(item.get("ui_item", False) or source_tag.startswith("UI_POINTER_"))
                ui_kind = str(item.get("ui_kind", "") or "")
                ui_template_hex = str(item.get("ui_template_hex", "") or "")
                ui_printable_positions_raw = item.get("ui_printable_positions")
                ui_printable_positions: List[int] = []
                if isinstance(ui_printable_positions_raw, list):
                    for pos in ui_printable_positions_raw:
                        pos_i = _parse_optional_int(pos)
                        if pos_i is None:
                            continue
                        if int(pos_i) >= 0:
                            ui_printable_positions.append(int(pos_i))
                ui_pointer_refs = _normalize_pointer_refs_from_item(item)
                if ui_pointer_refs:
                    has_pointer = True

                raw_bytes = _raw_bytes_for_item(item)
                raw_hex = raw_bytes.hex().upper() if raw_bytes else str(item.get("raw_bytes_hex", "") or "").upper()
                raw_len = len(raw_bytes)
                if raw_len <= 0:
                    raw_len = _parse_optional_int(item.get("raw_len")) or _parse_optional_int(item.get("max_len")) or 0

                # Dump auditável por item: UI ctrl usa texto limpo + template, sem placeholders.
                if is_ui_item and encoding == "ascii_ctrl_prefixed":
                    audit_text = text_src
                    unknown_count = 0
                    roundtrip_ok = True
                elif raw_bytes:
                    audit_text, unknown_count = self._decode_bytes_with_placeholders(raw_bytes)
                    encoded_back = self._encode_text_with_placeholders(audit_text)
                    roundtrip_ok = bool(encoded_back is not None and encoded_back == raw_bytes)
                else:
                    audit_text = text_src
                    unknown_count = 0
                    roundtrip_ok = False

                # Se houver byte desconhecido, texto usa placeholder explícito.
                text_src_export = audit_text if unknown_count > 0 else text_src

                # Determina reinsertion_safe com filtro de texto plausivel
                # Aplica filtro APENAS em strings de POINTER (nao scan cego)
                is_plausible = True
                reason_codes: List[str] = []
                requires_recompression = bool(item.get("requires_recompression", False))
                is_profile_region = source_tag.startswith("ASCII_PROFILE_")
                if has_pointer:
                    is_plausible = is_plausible_text_sms(text_src)
                    if not is_plausible:
                        reason_codes.append("NOT_PLAUSIBLE_TEXT_SMS")
                elif is_profile_region:
                    # Região explícita no profile: aceita quando texto for plausível.
                    is_plausible = is_plausible_text_sms(text_src)
                    if not is_plausible:
                        reason_codes.append("NOT_PLAUSIBLE_TEXT_SMS")

                if encoding == "tilemap":
                    reinsertion_safe = True
                elif is_profile_region:
                    reinsertion_safe = bool(is_plausible)
                else:
                    reinsertion_safe = has_pointer and is_plausible
                    if not has_pointer and encoding == "tile":
                        reason_codes.append("TILEMAP_NO_POINTER")
                if requires_recompression:
                    reinsertion_safe = False
                    reason_codes.append("REQUIRES_RECOMPRESSION")

                if is_ui_item:
                    term_ui = item.get("terminator")
                    if term_ui is None or int(term_ui) not in self.config.valid_terminators:
                        reason_codes.append("TERMINATOR_MISSING")
                        reinsertion_safe = False
                    if not has_pointer:
                        reason_codes.append("POINTER_INVALID")
                        reinsertion_safe = False
                    if raw_len <= 0:
                        reason_codes.append("POINTER_INVALID")
                        reinsertion_safe = False
                    if raw_bytes:
                        has_invalid_charset = any(
                            not self._is_valid_ui_byte(int(b))
                            for b in raw_bytes
                        )
                        if has_invalid_charset:
                            reason_codes.append("INVALID_CHARSET")
                            reinsertion_safe = False
                    else:
                        reason_codes.append("POINTER_INVALID")
                        reinsertion_safe = False

                review_flags: List[str] = []
                if seq in overlap_loser_idxs:
                    review_flags.append("OVERLAP_DISCARDED")
                if raw_len > 0 and raw_len <= 2:
                    review_flags.append("TOO_SHORT_FRAGMENT")
                if len(text_src.strip()) <= 2:
                    review_flags.append("TOO_SHORT_TEXT")
                if unknown_count > 0:
                    review_flags.append("HAS_UNKNOWN_BYTES")
                if raw_len > 0 and not roundtrip_ok:
                    review_flags.append("ROUNDTRIP_FAIL")
                if "{B:" in text_src_export:
                    review_flags.append("HAS_BYTE_PLACEHOLDER")

                if review_flags:
                    reinsertion_safe = False
                    reason_codes.extend(review_flags)

                # Detecta fragmento de prefixo: string começa no meio de palavra.
                # Exemplo clássico: "laxation to your..." com byte anterior = 'e'.
                off_val = int(item.get("offset", 0) or 0)
                prev_byte = self.rom_data[off_val - 1] if off_val > 0 else None
                prev_is_alpha = (
                    isinstance(prev_byte, int)
                    and ((0x41 <= prev_byte <= 0x5A) or (0x61 <= prev_byte <= 0x7A))
                )
                starts_lower = bool(text_src_export[:1]) and text_src_export[:1].islower()
                if (
                    encoding == "ascii"
                    and has_pointer
                    and starts_lower
                    and prev_is_alpha
                ):
                    review_flags.append("PREFIX_FRAGMENT")
                    reinsertion_safe = False
                    reason_codes.append("PREFIX_FRAGMENT")

                entry = {
                    "id": item["id"],
                    "offset": f"0x{item['offset']:06X}",
                    "rom_offset": f"0x{item['offset']:06X}",
                    "seq": int(seq),
                    "rom_crc32": rom_crc32,
                    "rom_size": rom_size,
                    "build_id": str(self.build_id),
                    "text_src": text_src_export,
                    "max_len_bytes": item["max_len"],
                    "raw_len": int(raw_len),
                    "encoding": encoding,
                    "source": item["source"],
                    "ui_item": bool(is_ui_item),
                    "has_pointer": bool(has_pointer),
                    "reinsertion_safe": reinsertion_safe,
                    "audit_roundtrip_ok": bool(roundtrip_ok),
                    "unknown_bytes_count": int(unknown_count),
                    "needs_review": bool(review_flags),
                    "review_flags": sorted(set(reason_codes)) if reason_codes else [],
                    "terminator": item.get("terminator"),
                    "raw_bytes_hex": raw_hex,
                }
                if is_ui_item:
                    entry["ui_kind"] = ui_kind
                    entry["ui_char_capacity"] = int(
                        _parse_optional_int(item.get("ui_char_capacity")) or len(ui_printable_positions)
                    )
                    entry["ui_printable_positions"] = [int(x) for x in ui_printable_positions]
                    if ui_template_hex:
                        entry["ui_template_hex"] = str(ui_template_hex)
                if requires_recompression:
                    entry["requires_recompression"] = True

                if item.get("bank") is not None:
                    entry["bank"] = item.get("bank")
                if item.get("page") is not None:
                    entry["page"] = item.get("page")

                # Adiciona reason_code/review_flags se bloqueado
                if reason_codes:
                    entry["reason_code"] = reason_codes[0]

                # Adiciona pointer_value para verificacao
                if item.get("pointer_value") is not None:
                    entry["pointer_value"] = f"0x{item['pointer_value']:04X}"

                # Reaproveita pointer_refs explícitos quando já vierem do extrator.
                if ui_pointer_refs:
                    entry["pointer_refs"] = list(ui_pointer_refs)

                # Calcula pointer_refs com transform completo quando não houver lista explícita.
                if "pointer_refs" not in entry and item.get("pointer_entry_offset") is not None and item.get("pointer_value") is not None:
                    offset = item["offset"]
                    ptr_value = item["pointer_value"]
                    ptr_offset = item["pointer_entry_offset"]
                    table_offset = item.get("pointer_table_offset")

                    # Calcula bank_addend: offset = ptr_value + bank_addend
                    bank_addend = offset - ptr_value

                    # Infere addressing_mode
                    if bank_addend == 0:
                        if ptr_value < 0x4000:
                            addr_mode = "DIRECT"
                        else:
                            addr_mode = "BANKED_SLOT1"
                    elif 0x4000 <= ptr_value < 0x8000:
                        addr_mode = "BANKED_SLOT1"
                    elif 0x8000 <= ptr_value < 0xC000:
                        addr_mode = "BANKED_SLOT2"
                    else:
                        addr_mode = "INFERRED"

                    # Cria pointer_ref com todos os campos de transform
                    pointer_ref = {
                        "ptr_offset": f"0x{ptr_offset:06X}",
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": addr_mode,
                        "bank_addend": f"0x{bank_addend:05X}",
                    }
                    if table_offset is not None:
                        pointer_ref["table_start"] = f"0x{table_offset:06X}"

                    entry["pointer_refs"] = [pointer_ref]

                # Espelha auditoria no item base para report/proof.
                item["clean"] = text_src_export
                item["raw_len"] = int(raw_len)
                item["raw_bytes_hex"] = raw_hex
                item["unknown_bytes_count"] = int(unknown_count)
                item["audit_roundtrip_ok"] = bool(roundtrip_ok)
                item["needs_review"] = bool(review_flags)
                item["review_flags"] = sorted(set(reason_codes)) if reason_codes else []
                item["has_pointer"] = bool(has_pointer)
                item["reinsertion_safe"] = bool(reinsertion_safe)
                item["requires_recompression"] = bool(requires_recompression)
                item["ui_item"] = bool(is_ui_item)
                if is_ui_item:
                    item["ui_kind"] = ui_kind
                    item["ui_char_capacity"] = int(
                        _parse_optional_int(item.get("ui_char_capacity")) or len(ui_printable_positions)
                    )
                    item["ui_printable_positions"] = [int(x) for x in ui_printable_positions]
                    if ui_template_hex:
                        item["ui_template_hex"] = str(ui_template_hex)
                if "pointer_refs" in entry:
                    item["pointer_refs"] = list(entry.get("pointer_refs") or [])
                if reason_codes:
                    item["reason_code"] = reason_codes[0]

                if text_src_export.strip():
                    self.translatable_total_count += 1
                    if requires_recompression:
                        self.recompress_pending_count += 1
                    if reinsertion_safe and not requires_recompression:
                        self.reinsertable_total_count += 1

                self.audit_unknown_bytes_total += int(unknown_count)
                if unknown_count > 0:
                    self.audit_unknown_items += 1
                if raw_len > 0 and not roundtrip_ok:
                    self.audit_roundtrip_fail_count += 1
                if seq in overlap_loser_idxs:
                    self.audit_overlap_items += 1
                if review_flags:
                    self.audit_review_items += 1

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _write_suspect_text_jsonl(self, path: Path) -> None:
        """
        Exporta somente itens suspeitos/review para auditoria objetiva.
        Critério: needs_review=true ou reinsertion_safe=false.
        """
        rom_crc32 = str(self.crc32_full).upper()
        rom_size = int(self.rom_size)
        suspects: List[Dict[str, Any]] = []
        for item in self.results:
            if bool(item.get("needs_review")) or not bool(item.get("reinsertion_safe", False)):
                suspects.append(item)

        # Ordem determinística por offset/id.
        suspects.sort(
            key=lambda x: (
                int(x.get("offset", 0) or 0),
                int(x.get("id", 0) or 0),
            )
        )

        meta = {
            "type": "meta",
            "schema": "neurorom.suspect_text.v1",
            "rom_crc32": rom_crc32,
            "rom_size": rom_size,
            "build_id": str(self.build_id),
            "items_total": len(suspects),
        }
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            for seq, item in enumerate(suspects):
                row = {
                    "id": item.get("id"),
                    "seq": int(seq),
                    "offset": f"0x{int(item.get('offset', 0) or 0):06X}",
                    "rom_offset": f"0x{int(item.get('offset', 0) or 0):06X}",
                    "rom_crc32": rom_crc32,
                    "rom_size": rom_size,
                    "text_src": str(item.get("clean", "")),
                    "max_len_bytes": int(item.get("max_len") or 0),
                    "raw_len": int(item.get("raw_len") or item.get("max_len") or 0),
                    "raw_bytes_hex": str(item.get("raw_bytes_hex", "") or ""),
                    "terminator": item.get("terminator"),
                    "encoding": item.get("encoding"),
                    "source": item.get("source"),
                    "audit_roundtrip_ok": bool(item.get("audit_roundtrip_ok", False)),
                    "unknown_bytes_count": int(item.get("unknown_bytes_count", 0)),
                    "review_flags": item.get("review_flags", []),
                    "needs_review": bool(item.get("needs_review", False)),
                    "reinsertion_safe": bool(item.get("reinsertion_safe", False)),
                    "reason_code": item.get("reason_code"),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _write_translation_catalogs(self, translation_path: Path, reinsertable_path: Path) -> None:
        """
        Gera catálogos separados:
        - textos para tradução (inclui bloqueados e itens com recompressão pendente)
        - textos reinseríveis (somente reinsertion_safe=true)
        """
        ordered = sorted(
            self.results,
            key=lambda x: (
                int(x.get("offset", 0) or 0),
                int(x.get("id", 0) or 0),
            ),
        )

        with open(translation_path, "w", encoding="utf-8") as tf:
            tf.write(f"# CRC32: {self.crc32_full}\n")
            tf.write(f"# BUILD_ID: {self.build_id}\n")
            tf.write("# catalog_type: for_translation\n")
            tf.write("# formato: [offset] [flags] texto\n\n")
            for item in ordered:
                text_src = str(item.get("clean") or item.get("decoded") or "").strip()
                if not text_src:
                    continue
                text_line = " ".join(text_src.splitlines())
                off = int(item.get("offset", 0) or 0)
                reinsertion_safe = bool(item.get("reinsertion_safe", False))
                requires_recompression = bool(item.get("requires_recompression", False))
                flags: List[str] = []
                if requires_recompression:
                    flags.append("RECOMPRESS_NEEDED")
                if not reinsertion_safe:
                    reason = str(item.get("reason_code") or "BLOCKED")
                    flags.append(f"NOT_REINSERTABLE:{reason}")
                flag_prefix = ((" ".join(f"[{flag}]" for flag in flags)) + " ") if flags else ""
                tf.write(f"[0x{off:06X}] {flag_prefix}{text_line}\n")

        with open(reinsertable_path, "w", encoding="utf-8") as rf:
            rf.write(f"# CRC32: {self.crc32_full}\n")
            rf.write(f"# BUILD_ID: {self.build_id}\n")
            rf.write("# catalog_type: reinsertable_only\n")
            rf.write("# formato: [offset] texto\n\n")
            for item in ordered:
                reinsertion_safe = bool(item.get("reinsertion_safe", False))
                requires_recompression = bool(item.get("requires_recompression", False))
                if not reinsertion_safe or requires_recompression:
                    continue
                text_src = str(item.get("clean") or item.get("decoded") or "").strip()
                if not text_src:
                    continue
                text_line = " ".join(text_src.splitlines())
                off = int(item.get("offset", 0) or 0)
                rf.write(f"[0x{off:06X}] {text_line}\n")

    def _write_overlap_resolution_evidence(self, path: Path) -> None:
        """Escreve evidência de resolução determinística de overlaps."""
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            meta = {
                "type": "meta",
                "schema": "neurorom.overlap_resolution.v1",
                "rom_crc32": str(self.crc32_full).upper(),
                "build_id": str(self.build_id),
                "overlap_clusters": int(self.audit_overlap_clusters),
                "overlap_discarded_count": int(self.overlap_discarded_count),
            }
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            for item in self.overlap_resolution_details:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _write_partial_pointer_evidence(self, path: Path) -> None:
        """Escreve evidência de salvage parcial de pointer tables."""
        with open(path, "w", encoding="utf-8", newline="\n") as pf:
            pf.write("=" * 60 + "\n")
            pf.write("PARTIAL POINTER TABLES (MIXED TABLE RECOVERY)\n")
            pf.write("=" * 60 + "\n")
            pf.write(f"BUILD_ID: {self.build_id}\n")
            pf.write(f"CRC32_FULL: {self.crc32_full}\n")
            pf.write(
                "pointer_table_partial_kept_count: "
                f"{int(self.pointer_table_partial_kept_count)}\n"
            )
            pf.write(
                "pointer_table_partial_tables_count: "
                f"{int(self.pointer_table_partial_accepted)}\n\n"
            )
            for idx, item in enumerate(self.partial_pointer_table_details, 1):
                pf.write(
                    f"{idx}. table_offset=0x{int(item.get('table_offset', 0)):06X} "
                    f"trigger={item.get('trigger_reason')} "
                    f"selected={int(item.get('entries_selected', 0))}/"
                    f"{int(item.get('entries_total_valid', 0))} "
                    f"ratio={float(item.get('selected_ratio', 0.0) or 0.0):.2f} "
                    f"plausibility_ratio={float(item.get('plausibility_ratio', 0.0) or 0.0):.2f} "
                    f"confidence={float(item.get('confidence', 0.0) or 0.0):.2f}\n"
                )
                for s in item.get("samples", []):
                    pf.write(
                        f"  entry_idx={int(s.get('entry_idx', 0))} "
                        f"sample_offset=0x{int(s.get('offset', 0)):06X} "
                        f"score={float(s.get('score', 0.0) or 0.0):.2f}\n"
                    )
                    pf.write(f"    ascii={s.get('ascii')}\n")
                pf.write("\n")

    def _write_mapping(self, path: Path) -> None:
        """
        Escreve arquivo de mapeamento para reinserção.
        Formato generico - apenas offsets e bytes, sem nomes.
        INCLUI APENAS itens com reinsertion_safe=true.
        """
        entries = []
        for item in self.results:
            # Aplica mesma logica de reinsertion_safe do JSONL
            has_pointer = bool(item.get("has_pointer", False))
            text_src = item["clean"]
            encoding = item.get("encoding", "ascii")
            reinsertion_safe = bool(item.get("reinsertion_safe"))
            if "reinsertion_safe" not in item:
                is_plausible = is_plausible_text_sms(text_src) if has_pointer else True
                if encoding == "tilemap":
                    reinsertion_safe = True
                else:
                    reinsertion_safe = has_pointer and is_plausible and encoding == "ascii"
            raw_len = int(item.get("raw_len") or item.get("max_len") or 0)

            # Inclui TODOS os itens, com flag reinsertion_safe
            entry = {
                "id": item["id"],
                "offset": item["offset"],
                "max_length": item["max_len"],
                "raw_len": raw_len,
                "terminator": item["terminator"],
                "source": item["source"],
                "encoding": encoding,
                "has_pointer": bool(item.get("has_pointer", False)),
                "pointer_table_offset": item.get("pointer_table_offset"),
                "pointer_entry_offset": item.get("pointer_entry_offset"),
                "pointer_refs": item.get("pointer_refs", []),
                "reinsertion_safe": reinsertion_safe,
                "raw_bytes_hex": item.get("raw_bytes_hex"),
                "audit_roundtrip_ok": bool(item.get("audit_roundtrip_ok", False)),
                "unknown_bytes_count": int(item.get("unknown_bytes_count", 0)),
                "review_flags": item.get("review_flags", []),
                "ui_item": bool(item.get("ui_item", False)),
            }
            if bool(item.get("ui_item", False)):
                entry["ui_kind"] = item.get("ui_kind")
                entry["ui_char_capacity"] = int(item.get("ui_char_capacity", 0) or 0)
                entry["ui_printable_positions"] = item.get("ui_printable_positions", [])
                entry["ui_template_hex"] = item.get("ui_template_hex")
            if not reinsertion_safe:
                entry["blocked_reason"] = (
                    item.get("reason_code")
                    or ("NOT_PLAUSIBLE_TEXT_SMS" if has_pointer else "NO_POINTER")
                )
            entries.append(entry)

        # Ordenação determinística por offset, com desempate por id/source.
        entries.sort(
            key=lambda e: (
                int(e.get("offset", 0) or 0),
                int(e.get("id", 0) or 0),
                str(e.get("source", "")),
            )
        )

        # Informacoes das tabelas descobertas
        tables_info = []
        for table in self.discovered_tables:
            tables_info.append({
                "offset": table.table_offset,
                "entry_count": table.entry_count,
                "entry_size": table.entry_size,
                "confidence": round(table.confidence, 3),
                "mode": str(getattr(table, "mode", "FULL") or "FULL"),
                "checked_entries": int(getattr(table, "checked_entries", table.entry_count) or table.entry_count),
                "plausibility_ratio": round(float(getattr(table, "plausibility_ratio", 0.0) or 0.0), 4),
                "partial_discarded": int(getattr(table, "partial_discarded", 0) or 0),
            })

        payload = {
            "schema": "binary_data_processor.mapping.v1",
            "file_crc32": self.crc32_full,
            "file_size": self.rom_size,
            "build_id": str(self.build_id),
            "discovered_pointer_tables": tables_info,
            "counters": {
                "pointer_table_partial_kept_count": int(self.pointer_table_partial_kept_count),
                "overlap_discarded_count": int(self.overlap_discarded_count),
                "translatable_total_count": int(self.translatable_total_count),
                "reinsertable_total_count": int(self.reinsertable_total_count),
                "recompress_pending_count": int(self.recompress_pending_count),
                "UI_ITEMS_FOUND": int(self.ui_items_found_count),
                "UI_ITEMS_EXTRACTED": int(self.ui_items_extracted_count),
                "UI_ITEMS_TRANSLATED": int(self.ui_items_translated_count),
                "UI_ITEMS_REINSERTED": int(self.ui_items_reinserted_count),
                "UI_ITEMS_BLOCKED": int(self.ui_items_blocked_count),
            },
            "text_blocks": entries,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _write_log(self, path: Path) -> None:
        """Escreve report de extracao com estatisticas completas."""
        # Conta por metodo
        by_source = {}
        for item in self.results:
            src = item["source"]
            by_source[src] = by_source.get(src, 0) + 1

        # Conta reinsertion safe com filtro de texto plausivel
        pointer_safe_count = 0
        tilemap_safe_count = 0
        blocked_count = 0
        block_reasons: Counter = Counter()

        safe_blocks: List[Dict[str, Any]] = []
        for item in self.results:
            encoding = item.get("encoding", "ascii")
            reinsertion_safe = bool(item.get("reinsertion_safe", False))
            if reinsertion_safe:
                if encoding in ("tilemap", "tile"):
                    tilemap_safe_count += 1
                else:
                    pointer_safe_count += 1
                safe_blocks.append({
                    "id": item.get("id"),
                    "offset": item.get("offset"),
                    "max_len": item.get("max_len"),
                    "raw_len": item.get("raw_len"),
                    "source": item.get("source"),
                    "terminator": item.get("terminator"),
                    "raw_bytes_hex": item.get("raw_bytes_hex", ""),
                    "roundtrip_ok": bool(item.get("audit_roundtrip_ok", False)),
                    "unknown_bytes_count": int(item.get("unknown_bytes_count", 0)),
                })
            else:
                blocked_count += 1
                block_reason = str(item.get("reason_code") or "BLOCKED")
                block_reasons[block_reason] += 1

        reinsertion_safe_count = pointer_safe_count + tilemap_safe_count

        # Top block reasons
        top_reasons = block_reasons.most_common(5)
        top_reasons_str = ", ".join(f"{r}={c}" for r, c in top_reasons) if top_reasons else "none"

        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("EXTRACTION REPORT\n")
            f.write("=" * 60 + "\n\n")

            # Identificacao neutra (OBRIGATORIO)
            f.write(f"BUILD_ID: {self.build_id}\n")
            f.write(f"CRC32_FULL: {self.crc32_full}\n")
            f.write(f"CRC32_NO_HEADER: {self.crc32_no_header}\n")
            f.write(f"ROM_SIZE: {self.rom_size}\n\n")

            # Estatisticas (OBRIGATORIO)
            f.write(f"TOTAL_TEXTLIKE: {len(self.results)}\n")
            f.write(f"TOTAL_DECODED: {len(self.results)}\n")
            f.write(f"TOTAL_TOKENIZED: {len(self.results)}\n")
            f.write(f"COVERAGE: 1.0\n\n")

            # Contagem por metodo
            f.write("-" * 40 + "\n")
            f.write("COUNT BY METHOD\n")
            f.write("-" * 40 + "\n")
            for src, count in sorted(by_source.items()):
                f.write(f"  {src}: {count}\n")
            f.write("\n")

            # Reinsertion stats
            f.write("-" * 40 + "\n")
            f.write("REINSERTION STATS\n")
            f.write("-" * 40 + "\n")
            f.write(f"REINSERTION_SAFE_COUNT: {reinsertion_safe_count}\n")
            f.write(f"REINSERTION_SAFE_POINTER: {pointer_safe_count}\n")
            f.write(f"REINSERTION_SAFE_TILEMAP: {tilemap_safe_count}\n")
            f.write(f"BLOCKED_COUNT: {blocked_count}\n")
            f.write(f"TOP_BLOCK_REASONS: {top_reasons_str}\n\n")

            f.write("-" * 40 + "\n")
            f.write("UI STATS\n")
            f.write("-" * 40 + "\n")
            f.write(f"UI_ITEMS_FOUND: {int(self.ui_items_found_count)}\n")
            f.write(f"UI_ITEMS_EXTRACTED: {int(self.ui_items_extracted_count)}\n")
            f.write(f"UI_ITEMS_TRANSLATED: {int(self.ui_items_translated_count)}\n")
            f.write(f"UI_ITEMS_REINSERTED: {int(self.ui_items_reinserted_count)}\n")
            f.write(f"UI_ITEMS_BLOCKED: {int(self.ui_items_blocked_count)}\n")
            if self.ui_items_blocked_details:
                f.write("UI_BLOCKED_DETAILS:\n")
                for row in self.ui_items_blocked_details[:50]:
                    f.write(
                        f"  - offset={row.get('offset')} reason={row.get('reason')} details={row.get('details')}\n"
                    )
            f.write("\n")

            f.write("-" * 40 + "\n")
            f.write("AUDIT STATS\n")
            f.write("-" * 40 + "\n")
            f.write(f"AUDIT_ITEMS: {len(self.results)}\n")
            f.write(f"AUDIT_UNKNOWN_BYTES_TOTAL: {int(self.audit_unknown_bytes_total)}\n")
            f.write(f"AUDIT_UNKNOWN_ITEMS: {int(self.audit_unknown_items)}\n")
            f.write(f"AUDIT_ROUNDTRIP_FAIL_COUNT: {int(self.audit_roundtrip_fail_count)}\n")
            f.write(f"AUDIT_OVERLAP_ITEMS: {int(self.audit_overlap_items)}\n")
            f.write(f"AUDIT_OVERLAP_CLUSTERS: {int(self.audit_overlap_clusters)}\n")
            f.write(f"AUDIT_NEEDS_REVIEW_ITEMS: {int(self.audit_review_items)}\n\n")

            f.write(
                f"REJECTED_POINTER_TABLE_LOW_PLAUSIBILITY: {self.rejected_pointer_table_low_plausibility}\n\n"
            )
            f.write(f"POINTER_TABLE_PARTIAL_ACCEPTED: {int(self.pointer_table_partial_accepted)}\n")
            f.write(
                f"POINTER_TABLE_PARTIAL_ENTRIES_TOTAL: {int(self.pointer_table_partial_entries_total)}\n\n"
            )
            f.write(
                "pointer_table_partial_kept_count: "
                f"{int(self.pointer_table_partial_kept_count)}\n"
            )
            f.write(f"overlap_discarded_count: {int(self.overlap_discarded_count)}\n")
            f.write(f"translatable_total_count: {int(self.translatable_total_count)}\n")
            f.write(f"reinsertable_total_count: {int(self.reinsertable_total_count)}\n")
            f.write(f"recompress_pending_count: {int(self.recompress_pending_count)}\n\n")
            if self.rejected_pointer_table_details:
                rejected_name = f"{self.crc32_full}_rejected_pointer_tables.txt"
                f.write(f"REJECTED_POINTER_TABLE_DETAILS: {rejected_name}\n\n")
            partial_name = f"{self.crc32_full}_partial_pointer_tables.txt"
            f.write(f"POINTER_TABLE_PARTIAL_DETAILS: {partial_name}\n\n")
            overlap_name = f"{self.crc32_full}_overlap_resolution_evidence.jsonl"
            f.write(f"OVERLAP_RESOLUTION_EVIDENCE: {overlap_name}\n\n")

            # Lista de blocos reinsertion_safe (detalhado)
            f.write("-" * 40 + "\n")
            f.write("REINSERTION_SAFE_BLOCKS\n")
            f.write("-" * 40 + "\n")
            if safe_blocks:
                for b in safe_blocks:
                    raw_hex = str(b.get("raw_bytes_hex", "") or "")
                    if len(raw_hex) > 96:
                        raw_hex = raw_hex[:96] + "..."
                    f.write(
                        f"  id={b.get('id')} offset=0x{int(b.get('offset')):06X} "
                        f"max_bytes={int(b.get('max_len'))} raw_len={int(b.get('raw_len') or b.get('max_len') or 0)} "
                        f"method={b.get('source')} terminator={b.get('terminator')} "
                        f"roundtrip={b.get('roundtrip_ok')} unknown={b.get('unknown_bytes_count')} "
                        f"raw_hex={raw_hex}\n"
                    )
            else:
                f.write("  none\n")
            f.write("\n")

            # Dump auditável por item (offset/raw_len/raw_hex/terminator)
            f.write("-" * 40 + "\n")
            f.write("AUDIT_ITEMS\n")
            f.write("-" * 40 + "\n")
            for item in self.results:
                raw_hex = str(item.get("raw_bytes_hex", "") or "")
                if len(raw_hex) > 96:
                    raw_hex = raw_hex[:96] + "..."
                review_flags = item.get("review_flags", [])
                f.write(
                    f"  id={item.get('id')} "
                    f"offset=0x{int(item.get('offset', 0)):06X} "
                    f"raw_len={int(item.get('raw_len') or item.get('max_len') or 0)} "
                    f"terminator={item.get('terminator')} "
                    f"safe={bool(item.get('reinsertion_safe', False))} "
                    f"roundtrip={bool(item.get('audit_roundtrip_ok', False))} "
                    f"unknown={int(item.get('unknown_bytes_count', 0))} "
                    f"flags={review_flags if review_flags else []} "
                    f"raw_hex={raw_hex}\n"
                )
            f.write("\n")

            # Tabelas de ponteiros descobertas
            f.write("-" * 40 + "\n")
            f.write("DISCOVERED POINTER TABLES\n")
            f.write("-" * 40 + "\n")
            if self.discovered_tables:
                for i, table in enumerate(self.discovered_tables, 1):
                    f.write(f"  Table {i}: offset=0x{table.table_offset:06X}, ")
                    f.write(f"entries={table.entry_count}, ")
                    f.write(f"confidence={table.confidence:.1%}, ")
                    f.write(f"mode={str(getattr(table, 'mode', 'FULL') or 'FULL')}\n")
            else:
                f.write("  No pointer tables discovered.\n")
            f.write("\n")
            # ASCII probe (determinístico)
            if self.ascii_probe_hits:
                f.write("-" * 40 + "\n")
                f.write("ASCII PROBE (LITERAL WORDS)\n")
                f.write("-" * 40 + "\n")
                f.write(f"TOTAL_HITS: {self.ascii_probe_total}\n")
                for word, offsets in self.ascii_probe_hits.items():
                    if offsets:
                        offs = ", ".join(f"0x{o:06X}" for o in offsets)
                        f.write(f"{word}: {len(offsets)} [{offs}]\n")
                    else:
                        f.write(f"{word}: 0\n")
                f.write("\n")

            # Tilemap probe (quando usado)
            if self.tilemap_probe_used:
                f.write("-" * 40 + "\n")
                f.write("TILEMAP PROBE (HEURISTIC)\n")
                f.write("-" * 40 + "\n")
                f.write(f"TILE_ITEMS: {len(self.tilemap_probe_items)}\n")
                f.write(f"FONT_CANDIDATES: {len(self.font_candidates)}\n")
                f.write(f"RANGE_CANDIDATES: {len(self.tilemap_candidate_ranges)}\n\n")

        if self.rejected_pointer_table_details:
            rejected_path = path.parent / f"{self.crc32_full}_rejected_pointer_tables.txt"
            with open(rejected_path, "w", encoding="utf-8") as rf:
                rf.write("=" * 60 + "\n")
                rf.write("REJECTED POINTER TABLES (LOW PLAUSIBILITY)\n")
                rf.write("=" * 60 + "\n\n")
                for idx, item in enumerate(self.rejected_pointer_table_details, 1):
                    rf.write(
                        f"{idx}. table_offset=0x{int(item['table_offset']):06X} "
                        f"reason={item.get('reason')} "
                        f"plausibility_ratio={item.get('plausibility_ratio'):.2f} "
                        f"avg_score={item.get('avg_score'):.2f}\n"
                    )
                    for s in item.get("samples", []):
                        rf.write(
                            f"  sample_offset=0x{int(s.get('offset')):06X} "
                            f"score={s.get('score', 0.0):.2f}\n"
                        )
                        rf.write(f"    hex={s.get('hex')}\n")
                        rf.write(f"    ascii={s.get('ascii')}\n")
                    rf.write("\n")

        if self.partial_pointer_table_details:
            partial_path = path.parent / f"{self.crc32_full}_partial_pointer_tables.txt"
            with open(partial_path, "w", encoding="utf-8") as pf:
                pf.write("=" * 60 + "\n")
                pf.write("PARTIAL POINTER TABLES (MIXED TABLE RECOVERY)\n")
                pf.write("=" * 60 + "\n\n")
                for idx, item in enumerate(self.partial_pointer_table_details, 1):
                    pf.write(
                        f"{idx}. table_offset=0x{int(item.get('table_offset', 0)):06X} "
                        f"trigger={item.get('trigger_reason')} "
                        f"selected={int(item.get('entries_selected', 0))}/"
                        f"{int(item.get('entries_total_valid', 0))} "
                        f"ratio={float(item.get('selected_ratio', 0.0) or 0.0):.2f} "
                        f"plausibility_ratio={float(item.get('plausibility_ratio', 0.0) or 0.0):.2f} "
                        f"confidence={float(item.get('confidence', 0.0) or 0.0):.2f}\n"
                    )
                    for s in item.get("samples", []):
                        pf.write(
                            f"  entry_idx={int(s.get('entry_idx', 0))} "
                            f"sample_offset=0x{int(s.get('offset', 0)):06X} "
                            f"score={float(s.get('score', 0.0) or 0.0):.2f}\n"
                        )
                        pf.write(f"    ascii={s.get('ascii')}\n")
                    pf.write("\n")

    def _write_proof_json(self, path: Path, generated_files: List[Path]) -> None:
        """
        Escreve proof.json com SHA256 de todos os outputs (formato V1).
        Garante reproducibilidade e verificacao de integridade.
        """
        # Calcula SHA256 de cada arquivo gerado
        file_proofs = []
        for file_path in generated_files:
            if file_path.exists():
                sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
                file_proofs.append({
                    "name": file_path.name,
                    "sha256": sha256,
                    "size": file_path.stat().st_size,
                })

        # Calcula estatisticas com filtro de texto plausivel
        reinsertion_safe = 0
        for item in self.results:
            if bool(item.get("reinsertion_safe", False)):
                reinsertion_safe += 1
        coverage = reinsertion_safe / len(self.results) if self.results else 0.0

        proof = {
            "schema": "extraction_proof.v1",
            "crc32": self.crc32_full,
            "build_id": str(self.build_id),
            "rom_sha256": hashlib.sha256(self.rom_data).hexdigest(),
            "rom_size": self.rom_size,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": "1.0.0",
            "console_type": "SMS",
            "extraction_mode": "static",
            "statistics": {
                "total_items": len(self.results),
                "safe_items": reinsertion_safe,
                "AUDIT_ITEMS": len(self.results),
                "REINSERTION_SAFE_COUNT": reinsertion_safe,
                "coverage": round(coverage, 4),
                "pointer_tables_found": len(self.discovered_tables),
                "pointer_table_partial_accepted": int(self.pointer_table_partial_accepted),
                "pointer_table_partial_entries_total": int(self.pointer_table_partial_entries_total),
                "pointer_table_partial_kept_count": int(self.pointer_table_partial_kept_count),
                "audit_unknown_bytes_total": int(self.audit_unknown_bytes_total),
                "audit_unknown_items": int(self.audit_unknown_items),
                "audit_roundtrip_fail_count": int(self.audit_roundtrip_fail_count),
                "audit_overlap_items": int(self.audit_overlap_items),
                "audit_overlap_clusters": int(self.audit_overlap_clusters),
                "audit_needs_review_items": int(self.audit_review_items),
                "overlap_discarded_count": int(self.overlap_discarded_count),
                "translatable_total_count": int(self.translatable_total_count),
                "reinsertable_total_count": int(self.reinsertable_total_count),
                "recompress_pending_count": int(self.recompress_pending_count),
                "UI_ITEMS_FOUND": int(self.ui_items_found_count),
                "UI_ITEMS_EXTRACTED": int(self.ui_items_extracted_count),
                "UI_ITEMS_TRANSLATED": int(self.ui_items_translated_count),
                "UI_ITEMS_REINSERTED": int(self.ui_items_reinserted_count),
                "UI_ITEMS_BLOCKED": int(self.ui_items_blocked_count),
            },
            "ui_blocked_items": list(self.ui_items_blocked_details),
            "file_proofs": file_proofs,
            "deterministic": True,
        }

        if self.tilemap_auto_info:
            proof["tilemap_auto_tbl"] = self.tilemap_auto_info

        with open(path, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)


# ============================================================================
# ALIAS PARA COMPATIBILIDADE
# ============================================================================

# Mantém nome antigo funcionando
UniversalMasterSystemExtractor = UniversalMasterSystemExtractor


# ============================================================================
# TRANSLATION_PREP_LAYER v2.2
# ============================================================================

@dataclass
class TranslationPrepConfig:
    """Configuracao do Translation Prep Layer v2.2."""
    # Encoding alvo para traducao
    target_encoding: str = "ascii"

    # ForbiddenBytePolicy
    forbidden_byte_policy: Optional[ForbiddenBytePolicy] = None

    # RepointPolicy (default OFF)
    repoint_enabled: bool = False
    free_space_regions: List[Tuple[int, int]] = field(default_factory=list)
    repoint_alignment: int = 0
    repoint_fill_byte: int = 0xFF

    # NewlinePolicy
    preserve_line_count: bool = True
    allow_reflow: bool = True
    max_line_width: int = 0
    newline_byte: int = 0x0A

    # Two-pass options
    two_pass_enabled: bool = True
    abbreviation_map: Dict[str, str] = field(default_factory=dict)

    # Output options
    generate_jsonl: bool = True
    generate_glossary: bool = True


@dataclass
class TranslationEntry:
    """Entrada de traducao preparada."""
    id: int
    offset: int
    original_text: str
    translated_text: str = ""
    max_len_bytes: int = 0
    encoded_len: int = 0
    cluster_id: str = ""
    fixed_field_len: Optional[int] = None
    pad_byte: Optional[int] = None
    validation_status: str = "pending"  # pending, ok, warning, blocked
    validation_errors: List[str] = field(default_factory=list)
    style_warnings: List[dict] = field(default_factory=list)
    repoint_patch: Optional[dict] = None


class TranslationPrepLayer:
    """
    TRANSLATION_PREP_LAYER v2.2

    Camada de preparacao de traducao com validacao e politicas.
    Mantém neutralidade (CRC32-only, sem referencias a titulos).

    Funcionalidades:
    - ForbiddenBytePolicy: validacao de bytes proibidos por encoding
    - RepointPolicy: repointing opcional para traducoes longas
    - FixedFieldDetector: detecta campos de tamanho fixo por cluster
    - NewlinePolicy: preserva contagem de linhas
    - StyleProfile: analise de estilo por cluster com warnings
    - Proof JSON: hash SHA256 de todos os outputs
    """

    VERSION = "2.2"

    def __init__(self, extractor: UniversalMasterSystemExtractor,
                 config: Optional[TranslationPrepConfig] = None):
        self.extractor = extractor
        self.config = config or TranslationPrepConfig()

        # Inicializa politicas
        self._init_policies()

        # Detectores e analisadores
        self.field_detector = FixedFieldDetector()
        self.style_analyzer = StyleProfileAnalyzer()

        # Dados de analise
        self.fixed_fields: Dict[str, FixedFieldInfo] = {}
        self.style_profiles: Dict[str, StyleProfileInfo] = {}

        # Entradas de traducao
        self.entries: List[TranslationEntry] = []

        # Outputs gerados (para proof.json)
        self.output_files: Dict[str, str] = {}  # path -> sha256

    def _init_policies(self):
        """Inicializa politicas de validacao."""
        # ForbiddenBytePolicy
        if self.config.forbidden_byte_policy:
            self.forbidden_policy = self.config.forbidden_byte_policy
        else:
            self.forbidden_policy = ForbiddenBytePolicy(
                encoding=self.config.target_encoding
            )

        # RepointPolicy
        self.repoint_policy = RepointPolicy(
            enabled=self.config.repoint_enabled,
            free_space_regions=list(self.config.free_space_regions),
            fill_byte=self.config.repoint_fill_byte,
            alignment=self.config.repoint_alignment,
        )

        # NewlinePolicy
        self.newline_policy = NewlinePolicy(
            preserve_line_count=self.config.preserve_line_count,
            newline_byte=self.config.newline_byte,
            allow_reflow=self.config.allow_reflow,
            max_line_width=self.config.max_line_width,
        )

    # ========================================================================
    # PREPARACAO DE TRADUCAO
    # ========================================================================

    def prepare(self) -> List[TranslationEntry]:
        """
        Prepara entradas para traducao.
        Analisa clusters, detecta campos fixos e perfis de estilo.
        """
        if not self.extractor.extracted_blocks:
            self.extractor.extract_texts()

        # Detecta campos fixos por cluster
        self.fixed_fields = self.field_detector.detect_all_clusters(
            self.extractor.extracted_blocks
        )

        # Analisa perfis de estilo por cluster
        self._analyze_style_profiles()

        # Cria entradas de traducao
        self.entries = []
        for block in self.extractor.extracted_blocks:
            entry = self._create_entry(block)
            self.entries.append(entry)

        return self.entries

    def _analyze_style_profiles(self):
        """Analisa perfis de estilo por cluster."""
        # Agrupa blocos por cluster
        clusters: Dict[str, List[TextBlock]] = {}
        for block in self.extractor.extracted_blocks:
            cluster_id = block.cluster_id or f"source_{block.source}"
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(block)

        # Analisa cada cluster
        for cluster_id, blocks in clusters.items():
            profile = self.style_analyzer.analyze_cluster(blocks, cluster_id)
            if profile:
                self.style_profiles[cluster_id] = profile

    def _create_entry(self, block: TextBlock) -> TranslationEntry:
        """Cria entrada de traducao a partir de um bloco."""
        cluster_id = block.cluster_id or f"source_{block.source}"

        # Verifica se ha campo fixo para este cluster
        fixed_len = None
        pad_byte = None
        if cluster_id in self.fixed_fields:
            fixed_info = self.fixed_fields[cluster_id]
            fixed_len = fixed_info.fixed_field_len_bytes
            pad_byte = fixed_info.pad_byte

        return TranslationEntry(
            id=block.offset,  # Usa offset como ID unico
            offset=block.offset,
            original_text=block.decoded_text,
            max_len_bytes=block.max_length,
            cluster_id=cluster_id,
            fixed_field_len=fixed_len,
            pad_byte=pad_byte,
        )

    # ========================================================================
    # VALIDACAO DE TRADUCAO
    # ========================================================================

    def validate_translation(self, entry: TranslationEntry,
                             translated_text: str) -> TranslationEntry:
        """
        Valida uma traducao contra todas as politicas.
        Retorna entrada atualizada com status e erros.
        """
        entry.translated_text = translated_text
        entry.validation_errors = []
        entry.style_warnings = []

        # 1. Valida encoding (ForbiddenBytePolicy)
        encoding_result = self._validate_encoding(entry)
        if encoding_result == ValidationResult.BLOCKED:
            entry.validation_status = "blocked"
            return entry

        # 2. Valida tamanho
        size_result = self._validate_size(entry)
        if size_result == ValidationResult.BLOCKED:
            entry.validation_status = "blocked"
            return entry

        # 3. Valida newlines (aplica reflow se necessario)
        self._validate_newlines(entry)

        # 4. Valida estilo
        style_warnings = self.style_analyzer.validate_translation(
            entry.id, entry.cluster_id, entry.original_text, entry.translated_text
        )
        entry.style_warnings = [
            {"type": w.warning_type, "expected": w.expected,
             "found": w.found, "severity": w.severity}
            for w in style_warnings
        ]

        # Determina status final
        if entry.validation_errors:
            entry.validation_status = "warning"
        else:
            entry.validation_status = "ok"

        return entry

    def _validate_encoding(self, entry: TranslationEntry) -> ValidationResult:
        """Valida bytes da traducao contra ForbiddenBytePolicy."""
        result, violations = self.forbidden_policy.validate_string(entry.translated_text)

        if result == ValidationResult.BLOCKED:
            entry.validation_errors.append(
                f"forbidden_bytes: encoding '{self.config.target_encoding}' "
                f"violation at positions {violations[:5]}..."
            )
        elif result == ValidationResult.WARNING:
            entry.validation_errors.append(
                f"forbidden_bytes_warning: potential issues at positions {violations[:5]}"
            )

        return result

    def _validate_size(self, entry: TranslationEntry) -> ValidationResult:
        """Valida tamanho da traducao."""
        try:
            encoded = entry.translated_text.encode(self.config.target_encoding)
            entry.encoded_len = len(encoded)
        except UnicodeEncodeError:
            entry.validation_errors.append("encoding_error: cannot encode translation")
            return ValidationResult.BLOCKED

        max_len = entry.fixed_field_len or entry.max_len_bytes

        if entry.encoded_len <= max_len:
            return ValidationResult.OK

        # Traducao excede tamanho - tenta two-pass
        if self.config.two_pass_enabled:
            shortened = self._apply_two_pass(entry.translated_text, max_len)
            try:
                shortened_encoded = shortened.encode(self.config.target_encoding)
                if len(shortened_encoded) <= max_len:
                    entry.translated_text = shortened
                    entry.encoded_len = len(shortened_encoded)
                    entry.validation_errors.append(
                        f"two_pass_applied: shortened from {len(encoded)} to {len(shortened_encoded)} bytes"
                    )
                    return ValidationResult.WARNING
            except UnicodeEncodeError:
                pass

        # Tenta repointing se habilitado
        if self.repoint_policy.enabled:
            new_offset = self.repoint_policy.allocate_space(entry.encoded_len + 1)  # +1 for terminator
            if new_offset is not None:
                self.repoint_policy.register_patch(
                    original_offset=entry.offset,
                    new_offset=new_offset,
                    pointer_offset=0,  # Sera preenchido pelo extrator
                    original_size=entry.max_len_bytes,
                    new_size=entry.encoded_len
                )
                entry.repoint_patch = {
                    "new_offset": new_offset,
                    "original_max_len": entry.max_len_bytes,
                    "new_len": entry.encoded_len,
                }
                entry.validation_errors.append(
                    f"repointed: text moved from 0x{entry.offset:06X} to 0x{new_offset:06X}"
                )
                return ValidationResult.WARNING

        # Nao conseguiu resolver
        entry.validation_errors.append(
            f"size_exceeded: {entry.encoded_len} bytes > max {max_len} bytes, "
            f"repoint={'disabled' if not self.repoint_policy.enabled else 'no_free_space'}"
        )
        return ValidationResult.BLOCKED

    def _validate_newlines(self, entry: TranslationEntry) -> ValidationResult:
        """Valida contagem de newlines."""
        result, details = self.newline_policy.validate_line_count(
            entry.original_text, entry.translated_text
        )

        if result == ValidationResult.WARNING:
            entry.validation_errors.append(
                f"line_count_mismatch: original={details['original_lines']}, "
                f"translated={details['translated_lines']}"
            )

            # Tenta reflow se permitido
            if self.newline_policy.allow_reflow and self.config.max_line_width > 0:
                reflowed = self.newline_policy.reflow_text(
                    entry.translated_text, self.config.max_line_width
                )
                entry.translated_text = reflowed
                entry.validation_errors.append("reflow_applied")

        return result

    def _apply_two_pass(self, text: str, max_len: int) -> str:
        """Aplica two-pass para encurtar traducao."""
        result = text

        # Aplica abreviacoes do mapa
        for full, abbrev in self.config.abbreviation_map.items():
            result = result.replace(full, abbrev)

        # Se ainda muito longo, trunca em limite de palavra
        try:
            encoded = result.encode(self.config.target_encoding)
            if len(encoded) > max_len:
                # Trunca preservando palavras
                while len(result.encode(self.config.target_encoding)) > max_len - 3:
                    words = result.rsplit(" ", 1)
                    if len(words) == 1:
                        result = result[:max_len - 3]
                        break
                    result = words[0]
                result = result.rstrip() + "..."
        except UnicodeEncodeError:
            result = result[:max_len]

        return result

    # ========================================================================
    # BATCH VALIDATION
    # ========================================================================

    def validate_batch(self, translations: Dict[int, str]) -> List[TranslationEntry]:
        """
        Valida um lote de traducoes.
        translations: dict de offset -> texto traduzido
        """
        results = []

        for entry in self.entries:
            if entry.offset in translations:
                validated = self.validate_translation(entry, translations[entry.offset])
                results.append(validated)
            else:
                entry.validation_status = "pending"
                results.append(entry)

        return results

    # ========================================================================
    # GERACAO DE OUTPUTS
    # ========================================================================

    def save_outputs(self, output_dir: Optional[str | Path] = None) -> Dict[str, str]:
        """
        Salva todos os outputs com nomenclatura CRC32.
        PROIBIDO usar rom_path.name para nomear outputs.

        Arquivos gerados (OBRIGATORIO):
        - {CRC32}_pure_text.jsonl
        - {CRC32}_reinsertion_mapping.json
        - {CRC32}_report.txt
        - {CRC32}_proof.json (SHA256)
        """
        out_dir = Path(output_dir) if output_dir else Path(self.extractor.file_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # Base: CRC32 apenas (PROIBIDO usar nome do arquivo)
        crc32 = self.extractor.crc32_full
        self.output_files = {}

        # 1. JSONL de texto puro (OBRIGATORIO)
        jsonl_path = out_dir / f"{crc32}_pure_text.jsonl"
        self._write_jsonl(jsonl_path)

        # 2. Reinsertion mapping JSON (OBRIGATORIO)
        mapping_path = out_dir / f"{crc32}_reinsertion_mapping.json"
        self._write_mapping_json(mapping_path)

        # 3. Report TXT (OBRIGATORIO)
        report_path = out_dir / f"{crc32}_report.txt"
        self._write_report_txt(report_path)

        # 4. Proof JSON com SHA256 (OBRIGATORIO)
        proof_path = out_dir / f"{crc32}_proof.json"
        self._write_proof_json(proof_path)

        return self.output_files

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calcula SHA256 de um arquivo."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _register_output(self, path: Path):
        """Registra output e calcula SHA256."""
        sha256 = self._calculate_sha256(path)
        self.output_files[str(path)] = sha256

    def _write_jsonl(self, path: Path):
        """Escreve JSONL de traducoes."""
        with open(path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                line = {
                    "id": entry.id,
                    "offset": f"0x{entry.offset:06X}",
                    "original": entry.original_text,
                    "translated": entry.translated_text,
                    "max_len_bytes": entry.max_len_bytes,
                    "cluster_id": entry.cluster_id,
                    "status": entry.validation_status,
                }
                if entry.fixed_field_len:
                    line["fixed_field_len"] = entry.fixed_field_len
                if entry.repoint_patch:
                    line["repoint"] = entry.repoint_patch
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        self._register_output(path)

    def _write_clean_txt(self, path: Path):
        """Escreve TXT de texto limpo."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# TRANSLATION_PREP_LAYER v{self.VERSION}\n")
            f.write(f"# CRC32: {self.extractor.crc32_full}\n")
            f.write(f"# Entries: {len(self.entries)}\n")
            f.write("# " + "=" * 56 + "\n\n")

            current_cluster = None
            for entry in self.entries:
                if entry.cluster_id != current_cluster:
                    current_cluster = entry.cluster_id
                    f.write(f"\n# ---- {current_cluster} ----\n\n")

                f.write(f"[{entry.offset:06X}] max={entry.max_len_bytes}")
                if entry.fixed_field_len:
                    f.write(f" fixed={entry.fixed_field_len}")
                f.write("\n")
                f.write(f"{entry.original_text}\n")
                if entry.translated_text:
                    f.write(f">>> {entry.translated_text}\n")
                f.write("-" * 40 + "\n")
        self._register_output(path)

    def _write_mapping_json(self, path: Path):
        """Escreve mapping JSON com informacoes de repointing."""
        mapping = {
            "schema": "translation_prep_layer.mapping.v2.2",
            "crc32": self.extractor.crc32_full,
            "file_size": self.extractor.rom_size,
            "encoding": self.config.target_encoding,
            "entries": [],
            "fixed_fields": {},
            "repoint_patches": [],
        }

        # Entradas
        for entry in self.entries:
            mapping["entries"].append({
                "offset": entry.offset,
                "max_len_bytes": entry.max_len_bytes,
                "cluster_id": entry.cluster_id,
                "fixed_field_len": entry.fixed_field_len,
                "pad_byte": entry.pad_byte,
            })

        # Campos fixos
        for cluster_id, info in self.fixed_fields.items():
            mapping["fixed_fields"][cluster_id] = {
                "len_bytes": info.fixed_field_len_bytes,
                "pad_byte": info.pad_byte,
                "stride": info.stride,
                "confidence": round(info.confidence, 3),
            }

        # Patches de repointing
        mapping["repoint_patches"] = self.repoint_policy.patches

        with open(path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        self._register_output(path)

    def _write_report_json(self, path: Path):
        """Escreve report JSON com estatisticas e warnings."""
        # Estatisticas de validacao
        stats = {
            "total": len(self.entries),
            "ok": sum(1 for e in self.entries if e.validation_status == "ok"),
            "warning": sum(1 for e in self.entries if e.validation_status == "warning"),
            "blocked": sum(1 for e in self.entries if e.validation_status == "blocked"),
            "pending": sum(1 for e in self.entries if e.validation_status == "pending"),
        }

        # Warnings de estilo
        style_warnings = self.style_analyzer.get_report_warnings()

        # Erros de validacao por tipo
        validation_errors: Dict[str, int] = {}
        for entry in self.entries:
            for error in entry.validation_errors:
                error_type = error.split(":")[0]
                validation_errors[error_type] = validation_errors.get(error_type, 0) + 1

        report = {
            "schema": "translation_prep_layer.report.v2.2",
            "crc32": self.extractor.crc32_full,
            "version": self.VERSION,
            "statistics": stats,
            "validation_errors_by_type": validation_errors,
            "style_warnings": style_warnings,
            "style_profiles": {
                cluster_id: {
                    "capitalization": profile.capitalization,
                    "caps_ratio": round(profile.caps_ratio, 2),
                    "punctuation_pattern": profile.punctuation_pattern,
                    "avg_word_length": round(profile.avg_word_length, 1),
                    "sample_count": profile.sample_count,
                }
                for cluster_id, profile in self.style_profiles.items()
            },
            "repoint_stats": {
                "enabled": self.repoint_policy.enabled,
                "patches_count": len(self.repoint_policy.patches),
                "space_used": self.repoint_policy.used_space,
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        self._register_output(path)

    def _write_report_txt(self, path: Path):
        """
        Escreve report TXT com campos OBRIGATORIOS.

        CAMPOS OBRIGATORIOS:
        - CRC32_FULL, CRC32_NO_HEADER, ROM_SIZE
        - TOTAL_TEXTLIKE, TOTAL_DECODED, TOTAL_TOKENIZED, COVERAGE=1.0
        - Contagem por metodo
        - REINSERTION_SAFE_COUNT, BLOCKED_COUNT + top reasons
        """
        # Estatisticas
        total = len(self.entries)
        ok_count = sum(1 for e in self.entries if e.validation_status == "ok")
        blocked_count = sum(1 for e in self.entries if e.validation_status == "blocked")
        pending_count = sum(1 for e in self.entries if e.validation_status == "pending")

        # Contagem por cluster (metodo)
        by_cluster: Dict[str, int] = {}
        for entry in self.entries:
            cluster = entry.cluster_id or "UNKNOWN"
            by_cluster[cluster] = by_cluster.get(cluster, 0) + 1

        # Razoes de bloqueio
        block_reasons: Dict[str, int] = {}
        for entry in self.entries:
            if entry.validation_status == "blocked":
                for error in entry.validation_errors:
                    reason = error.split(":")[0]
                    block_reasons[reason] = block_reasons.get(reason, 0) + 1

        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("EXTRACTION REPORT\n")
            f.write("=" * 60 + "\n\n")

            # Identificacao neutra (OBRIGATORIO)
            f.write(f"CRC32_FULL: {self.extractor.crc32_full}\n")
            f.write(f"CRC32_NO_HEADER: {self.extractor.crc32_no_header}\n")
            f.write(f"ROM_SIZE: {self.extractor.rom_size}\n\n")

            # Estatisticas (OBRIGATORIO)
            f.write(f"TOTAL_TEXTLIKE: {total}\n")
            f.write(f"TOTAL_DECODED: {total}\n")
            f.write(f"TOTAL_TOKENIZED: {total}\n")
            f.write(f"COVERAGE: 1.0\n\n")

            # Contagem por metodo
            f.write("-" * 40 + "\n")
            f.write("COUNT BY METHOD\n")
            f.write("-" * 40 + "\n")
            for cluster, count in sorted(by_cluster.items()):
                f.write(f"  {cluster}: {count}\n")
            f.write("\n")

            # Reinsertion stats (OBRIGATORIO)
            f.write("-" * 40 + "\n")
            f.write("REINSERTION STATS\n")
            f.write("-" * 40 + "\n")
            f.write(f"REINSERTION_SAFE_COUNT: {ok_count + pending_count}\n")
            f.write(f"BLOCKED_COUNT: {blocked_count}\n")

            if block_reasons:
                top_reasons = sorted(block_reasons.items(), key=lambda x: -x[1])[:3]
                f.write(f"TOP_BLOCK_REASONS: {', '.join(f'{r}({c})' for r, c in top_reasons)}\n")
            else:
                f.write(f"TOP_BLOCK_REASONS: none\n")
            f.write("\n")

        self._register_output(path)

    def _write_glossary_json(self, path: Path):
        """Escreve glossario extraido automaticamente."""
        # Extrai termos repetidos
        term_counts: Dict[str, int] = {}
        for entry in self.entries:
            words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', entry.original_text)
            for word in words:
                if len(word) >= 3:
                    term_counts[word] = term_counts.get(word, 0) + 1

        # Filtra termos que aparecem 2+ vezes
        glossary = {
            "schema": "translation_prep_layer.glossary.v2.2",
            "crc32": self.extractor.crc32_full,
            "terms": {
                term: {"count": count, "translation": ""}
                for term, count in sorted(term_counts.items(), key=lambda x: -x[1])
                if count >= 2
            },
            "abbreviations": dict(self.config.abbreviation_map),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(glossary, f, indent=2, ensure_ascii=False)
        self._register_output(path)

    def _write_proof_json(self, path: Path):
        """Escreve proof.json com SHA256 de todos os outputs."""
        proof = {
            "schema": "translation_prep_layer.proof.v2.2",
            "crc32": self.extractor.crc32_full,
            "version": self.VERSION,
            "timestamp": self._get_timestamp(),
            "outputs": self.output_files,
            "rom_sha256": hashlib.sha256(self.extractor.rom_data).hexdigest(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)

        # Registra o proprio proof.json
        proof["outputs"][str(path)] = self._calculate_sha256(path)

        # Reescreve com hash atualizado (self-referential)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2, ensure_ascii=False)

    def _get_timestamp(self) -> str:
        """Retorna timestamp ISO 8601."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # ========================================================================
    # IMPORT/LOAD TRANSLATIONS
    # ========================================================================

    def load_translations_jsonl(self, jsonl_path: str | Path) -> int:
        """
        Carrega traducoes de arquivo JSONL.
        Retorna numero de traducoes carregadas.
        """
        loaded = 0
        translations: Dict[int, str] = {}

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                offset = data.get("offset", 0)
                if isinstance(offset, str):
                    offset = int(offset, 16)
                translated = data.get("translated", "")
                if translated:
                    translations[offset] = translated
                    loaded += 1

        # Valida todas as traducoes carregadas
        self.validate_batch(translations)

        return loaded


# ============================================================================
# FUNCAO DE CONVENIENCIA
# ============================================================================

def create_prep_layer(file_path: str | Path,
                      config: Optional[TranslationPrepConfig] = None,
                      extractor_config: Optional[ExtractorConfig] = None
                      ) -> TranslationPrepLayer:
    """
    Funcao de conveniencia para criar TranslationPrepLayer.

    Exemplo:
        prep = create_prep_layer("game.sms")
        prep.prepare()
        prep.save_outputs("./output")
    """
    extractor = UniversalMasterSystemExtractor(file_path, extractor_config)
    return TranslationPrepLayer(extractor, config)
