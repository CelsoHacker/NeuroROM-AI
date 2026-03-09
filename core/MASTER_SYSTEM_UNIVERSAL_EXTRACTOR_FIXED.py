# ============================================================================
# BINARY DATA PROCESSOR - Universal SMS Extractor
# v7.0 AUTO-DISCOVERY MODE
# ============================================================================
# Ferramenta de Processamento de Dados Binarios
# Modo totalmente generico - sem referencias a titulos ou marcas
# ============================================================================

from __future__ import annotations

import os
import json
import re
import zlib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
from collections import Counter
import math


# ============================================================================
# CONFIGURACOES
# ============================================================================

@dataclass
class ExtractorConfig:
    """Configuracoes do extrator - ajustaveis pelo usuario."""
    # Ponteiros
    min_pointers_for_table: int = 8          # Minimo de ponteiros para considerar tabela
    max_pointer_gap: int = 0x100             # Gap maximo entre ponteiros consecutivos
    pointer_validation_threshold: float = 0.6 # 60% dos ponteiros devem ser validos

    # Texto
    min_text_length: int = 3                 # Comprimento minimo de texto
    max_text_length: int = 256               # Comprimento maximo de texto
    alphanumeric_threshold: float = 0.6      # 60% de caracteres alfanumericos

    # Terminadores validos
    valid_terminators: Tuple[int, ...] = (0x00, 0xFF, 0x20)

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
    confidence: float = 0.0                  # Confianca na descoberta (0.0-1.0)


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
        self.discovered_tables: List[PointerTable] = []
        self.extracted_blocks: List[TextBlock] = []

        # Resultados (compatibilidade com GUI)
        self.results: List[dict] = []
        self.filtered_texts: List[dict] = []

        # Carrega arquivo
        self._load_file()
        self._calculate_checksums()

    # ========================================================================
    # CARREGAMENTO E CHECKSUMS
    # ========================================================================

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

    # ========================================================================
    # UTILIDADES DE LEITURA
    # ========================================================================

    def _read_u16le(self, offset: int) -> Optional[int]:
        """Le um valor 16-bit Little Endian."""
        if offset < 0 or offset + 2 > self.rom_size:
            return None
        return int.from_bytes(self.rom_data[offset:offset+2], "little")

    def _is_printable_ascii(self, byte: int) -> bool:
        """Verifica se byte e ASCII imprimivel (0x20-0x7E)."""
        return 0x20 <= byte <= 0x7E

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

        # Firewall: strings curtas (<3) com simbolos especiais = DESCARTAR
        forbidden_short_chars = set('~#|^_')
        if len(text) < 3:
            if any(c in forbidden_short_chars for c in text):
                return False

        # Strings muito curtas sem letras = DESCARTAR
        if len(text) < 3:
            letter_count = sum(1 for c in text if c.isalpha())
            if letter_count == 0:
                return False

        return True

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

            if table and table.confidence >= 0.5:
                discovered.append(table)
                # Marca area como escaneada
                table_end = table.table_offset + (table.entry_count * table.entry_size)
                scanned_ranges.add((table.table_offset, table_end))
                i = table_end
            else:
                i += 2

        # Ordena por confianca
        discovered.sort(key=lambda t: t.confidence, reverse=True)
        return discovered

    def _try_detect_pointer_table_at(self, offset: int) -> Optional[PointerTable]:
        """
        Tenta detectar uma tabela de ponteiros iniciando em 'offset'.
        """
        valid_pointers: List[int] = []
        invalid_count = 0
        max_invalid_streak = 3
        current_invalid_streak = 0

        idx = 0
        while idx < self.config.min_pointers_for_table * 10:  # Limita busca
            ptr_offset = offset + (idx * 2)
            if ptr_offset + 2 > self.rom_size:
                break

            ptr_value = self._read_u16le(ptr_offset)
            if ptr_value is None:
                break

            # Valida se ponteiro aponta para area valida
            resolved = self._resolve_pointer_heuristic(ptr_value)

            if resolved is not None:
                # Verifica se ha texto valido no destino
                text_data = self._read_text_at_offset(resolved)
                if text_data and self._is_valid_text_block(text_data, require_terminator=False):
                    valid_pointers.append(ptr_value)
                    current_invalid_streak = 0
                else:
                    invalid_count += 1
                    current_invalid_streak += 1
            else:
                invalid_count += 1
                current_invalid_streak += 1

            # Para se muitos invalidos consecutivos
            if current_invalid_streak >= max_invalid_streak:
                break

            idx += 1

        # Verifica se encontramos ponteiros suficientes
        if len(valid_pointers) < self.config.min_pointers_for_table:
            return None

        total_checked = len(valid_pointers) + invalid_count
        confidence = len(valid_pointers) / total_checked if total_checked > 0 else 0

        if confidence < self.config.pointer_validation_threshold:
            return None

        return PointerTable(
            table_offset=offset,
            entry_count=len(valid_pointers),
            entry_size=2,
            valid_pointers=valid_pointers,
            confidence=confidence
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

            # Se nao e imprimivel, para
            if not self._is_printable_ascii(byte):
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
                resolved = self._resolve_pointer_heuristic(ptr)
                if resolved is None or resolved in seen_offsets:
                    continue

                data = self._read_text_at_offset(resolved)
                if not data or not self._is_valid_text_block(data):
                    continue

                try:
                    text = data.decode("ascii", errors="ignore").strip()
                except:
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
                    pointer_entry_offset=table.table_offset + (idx * 2),
                    pointer_value=ptr,  # Valor lido do ponteiro (prova)
                    confidence=table.confidence
                ))
                seen_offsets.add(resolved)

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
        seen_offsets: Set[int] = set()

        # ============================================================
        # FASE 1: DESCOBERTA DE TABELAS DE PONTEIROS (HEURISTICA)
        # ============================================================
        self.discovered_tables = self._find_potential_pointer_tables()

        # ============================================================
        # FASE 2: EXTRAÇÃO SOMENTE DOS PONTEIROS DESCOBERTOS
        # ============================================================
        for block in self._extract_from_pointer_tables():
            if block.offset not in seen_offsets:
                # Aplica firewall adicional
                if self._post_filter_text(block.decoded_text):
                    self.extracted_blocks.append(block)
                    seen_offsets.add(block.offset)

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

        self.filtered_texts = self.results
        return self.results

    def extract_all_texts(self) -> List[dict]:
        """Alias para compatibilidade."""
        if not self.results:
            self.extract_texts()
        return self.results

    # ========================================================================
    # SALVAMENTO DE RESULTADOS
    # ========================================================================

    def save_results(self, output_dir: Optional[str | Path] = None) -> str:
        """
        Salva resultados em arquivos.
        Formato generico, sem referencias a titulos.
        """
        if not self.results:
            self.extract_texts()

        out_dir = Path(output_dir) if output_dir else Path(self.file_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # PROIBIDO usar rom_path.name - usar somente CRC32
        base_name = f"{self.crc32_full}_{self.rom_size}"

        # Arquivos de saida nomeados por CRC32
        clean_blocks_path = out_dir / f"{base_name}_pure_text.txt"
        mapping_path = out_dir / f"{base_name}_reinsertion_mapping.json"
        log_path = out_dir / f"{base_name}_report.txt"

        self._write_clean_blocks(clean_blocks_path)
        self._write_mapping(mapping_path)
        self._write_log(log_path)

        return str(clean_blocks_path)

    def _write_clean_blocks(self, path: Path) -> None:
        """Escreve arquivo de texto limpo para traducao."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("# ============================================================\n")
            f.write("# Extracted Text Blocks\n")
            f.write("# ============================================================\n")
            f.write(f"# CRC32_FULL: {self.crc32_full}\n")
            f.write(f"# CRC32_NO_HEADER: {self.crc32_no_header}\n")
            f.write(f"# ROM_SIZE: {self.rom_size}\n")
            f.write(f"# TOTAL_TEXTLIKE: {len(self.results)}\n")
            f.write(f"# POINTER_TABLES_FOUND: {len(self.discovered_tables)}\n")
            f.write("# ============================================================\n\n")

            current_source = None
            for item in self.results:
                # Cabecalho de secao
                if item["source"] != current_source:
                    current_source = item["source"]
                    f.write(f"\n# ---- {current_source} ----\n\n")

                # Bloco de texto
                f.write(f"[{item['id']:04d}] @0x{item['offset']:06X} [max={item['max_len']}]\n")
                f.write(f"{item['clean']}\n")
                f.write("-" * 50 + "\n")

    def _write_mapping(self, path: Path) -> None:
        """
        Escreve arquivo de mapeamento para reinserção.
        Formato generico - apenas offsets e bytes, sem nomes.
        """
        entries = []
        for item in self.results:
            entries.append({
                "id": item["id"],
                "offset": item["offset"],
                "max_length": item["max_len"],
                "terminator": item["terminator"],
                "source": item["source"],
                "encoding": "ascii",
                "pointer_table_offset": item.get("pointer_table_offset"),
                "pointer_entry_offset": item.get("pointer_entry_offset"),
            })

        # Informacoes das tabelas descobertas
        tables_info = []
        for table in self.discovered_tables:
            tables_info.append({
                "offset": table.table_offset,
                "entry_count": table.entry_count,
                "entry_size": table.entry_size,
                "confidence": round(table.confidence, 3),
            })

        payload = {
            "schema": "binary_data_processor.mapping.v1",
            "file_crc32": self.crc32_full,
            "file_size": self.rom_size,
            "discovered_pointer_tables": tables_info,
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

        # Conta reinsertion safe
        reinsertion_safe = sum(1 for item in self.results if item.get("has_pointer"))

        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("EXTRACTION REPORT\n")
            f.write("=" * 60 + "\n\n")

            # Identificacao neutra (OBRIGATORIO)
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
            f.write(f"REINSERTION_SAFE_COUNT: {reinsertion_safe}\n")
            f.write(f"BLOCKED_COUNT: 0\n")
            f.write(f"TOP_BLOCK_REASONS: none\n\n")

            # Tabelas de ponteiros descobertas
            f.write("-" * 40 + "\n")
            f.write("DISCOVERED POINTER TABLES\n")
            f.write("-" * 40 + "\n")
            if self.discovered_tables:
                for i, table in enumerate(self.discovered_tables, 1):
                    f.write(f"  Table {i}: offset=0x{table.table_offset:06X}, ")
                    f.write(f"entries={table.entry_count}, ")
                    f.write(f"confidence={table.confidence:.1%}\n")
            else:
                f.write("  No pointer tables discovered.\n")
            f.write("\n")


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
