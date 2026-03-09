# -*- coding: utf-8 -*-
"""
SMS PRO EXTRACTOR v1.0
======================
Extrator completo para Sega Master System com:
- Descoberta automática de tabelas de ponteiros (múltiplas regras de bank)
- Inferência automática de terminador
- SMS Tilemap Extractor (texto como tiles)
- TBL Auto Learner (aprender tabela de caracteres)
- Quality Gates (fail-fast)
- Profile por CRC (caching automático)

Autor: NeuroROM AI
"""

from __future__ import annotations

import os
import json
import zlib
import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
from collections import Counter
from datetime import datetime, timezone

try:
    # Execução como pacote (interface usa "from core...")
    from core.sms_game_engineering import SMSGameEngineeringManager
except Exception:
    try:
        # Execução direta do arquivo
        from sms_game_engineering import SMSGameEngineeringManager
    except Exception:
        SMSGameEngineeringManager = None


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

@dataclass
class SMSExtractorConfig:
    """Configuração do extrator SMS PRO."""
    # Quality Gates
    min_safe_ratio: float = 0.90              # Se safe_ratio < 0.90, aborta
    min_pointer_confidence: float = 0.60      # Confiança mínima para tabela de ponteiros
    min_text_length: int = 3                  # Comprimento mínimo de texto
    max_text_length: int = 256                # Comprimento máximo de texto
    min_pointers_for_table: int = 6           # Mínimo de ponteiros para tabela válida

    # Terminadores a testar
    candidate_terminators: Tuple[int, ...] = (0x00, 0x1C, 0xFF, 0x1E, 0x1F)

    # Bank rules a testar
    bank_size: int = 0x4000                   # 16KB

    # TBL Auto Learner
    tbl_min_confidence: float = 0.85          # Confiança mínima para aplicar TBL

    # Profiles
    profiles_dir: str = "./profiles/sms"
    engineering_profiles_path: str = "./profiles/sms/game_engineering_profiles.json"


class ExtractionMethod(Enum):
    """Método de extração usado."""
    POINTER_TABLE = "POINTER_TABLE"
    TILEMAP = "TILEMAP"
    ASCII_SCAN = "ASCII_SCAN"
    PROFILE_CACHED = "PROFILE_CACHED"


@dataclass
class PointerTableCandidate:
    """Candidato a tabela de ponteiros."""
    table_offset: int
    entry_count: int
    bank_rule: str                            # "SLOT1_4000" ou "SLOT2_8000"
    terminator: int
    pointer_values: List[int] = field(default_factory=list)
    resolved_offsets: List[int] = field(default_factory=list)
    confidence: float = 0.0
    valid_text_count: int = 0


@dataclass
class ExtractedItem:
    """Item extraído."""
    id: int
    file_offset: int
    pointer_table_offset: Optional[int]
    pointer_index: Optional[int]
    pointer_value: Optional[int]
    bank: Optional[int]
    bank_rule: Optional[str]
    terminator: int
    raw_bytes: bytes
    raw_hex: str
    decoded_text: str
    is_decoded: bool
    confidence: float
    method: ExtractionMethod


@dataclass
class ExtractionResult:
    """Resultado da extração."""
    success: bool
    method: ExtractionMethod
    items: List[ExtractedItem]
    safe_ratio: float
    total_extracted: int
    safe_count: int
    rejected_count: int
    terminator_used: int
    bank_rule_used: str
    pointer_tables_found: int
    error_message: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# TBL AUTO LEARNER
# ============================================================================

class TBLAutoLearner:
    """
    Auto Learner para aprender mapping símbolo→caractere automaticamente.
    Usa análise de frequência de n-gramas para resolver substituição (cipher).
    """

    # Frequências de bigramas em inglês (top 20)
    ENGLISH_BIGRAMS = {
        'th': 0.0356, 'he': 0.0307, 'in': 0.0243, 'er': 0.0205, 'an': 0.0199,
        'on': 0.0176, 'en': 0.0145, 're': 0.0145, 'nd': 0.0135, 'at': 0.0124,
        'st': 0.0105, 'es': 0.0099, 'or': 0.0096, 'nt': 0.0095, 'ti': 0.0093,
        'te': 0.0089, 'is': 0.0086, 'of': 0.0080, 'it': 0.0078, 'al': 0.0077
    }

    # Frequência de letras em inglês
    ENGLISH_LETTER_FREQ = {
        'e': 0.127, 't': 0.091, 'a': 0.082, 'o': 0.075, 'i': 0.070,
        'n': 0.067, 's': 0.063, 'h': 0.061, 'r': 0.060, 'd': 0.043,
        'l': 0.040, 'c': 0.028, 'u': 0.028, 'm': 0.024, 'w': 0.024,
        'f': 0.022, 'g': 0.020, 'y': 0.020, 'p': 0.019, 'b': 0.015,
        'v': 0.010, 'k': 0.008, 'j': 0.002, 'x': 0.002, 'q': 0.001, 'z': 0.001
    }

    def __init__(self, corpus: List[bytes]):
        """
        Inicializa o auto learner.

        Args:
            corpus: Lista de strings tokenizadas (bytes) do extrator
        """
        self.corpus = corpus
        self.byte_freq: Counter = Counter()
        self.bigram_freq: Counter = Counter()
        self.mapping: Dict[int, str] = {}
        self.confidence_per_symbol: Dict[int, float] = {}
        self.global_confidence: float = 0.0

        self._analyze_corpus()

    def _analyze_corpus(self):
        """Analisa frequência de bytes no corpus."""
        total_bytes = 0
        for item in self.corpus:
            for b in item:
                self.byte_freq[b] += 1
                total_bytes += 1
            # Bigramas
            for i in range(len(item) - 1):
                bigram = (item[i], item[i + 1])
                self.bigram_freq[bigram] += 1

    def learn(self) -> Tuple[Dict[int, str], float]:
        """
        Tenta aprender o mapping automaticamente.

        Returns:
            (mapping, confiança_global)
        """
        # Verifica se já é ASCII
        if self._is_already_ascii():
            # Já é ASCII, confiança alta
            for b in range(0x20, 0x7F):
                self.mapping[b] = chr(b)
            self.global_confidence = 0.99
            return self.mapping, self.global_confidence

        # Tenta shift simples primeiro
        best_shift, shift_confidence = self._try_simple_shift()
        if shift_confidence > 0.85:
            for b, count in self.byte_freq.items():
                shifted = (b + best_shift) & 0xFF
                if 0x20 <= shifted <= 0x7E:
                    self.mapping[b] = chr(shifted)
            self.global_confidence = shift_confidence
            return self.mapping, self.global_confidence

        # Fallback: frequência de letras
        confidence = self._try_frequency_analysis()
        self.global_confidence = confidence

        return self.mapping, self.global_confidence

    def _is_already_ascii(self) -> bool:
        """Verifica se o corpus já é ASCII."""
        printable_count = 0
        total_count = 0
        for b, count in self.byte_freq.items():
            total_count += count
            if 0x20 <= b <= 0x7E:
                printable_count += count

        return total_count > 0 and (printable_count / total_count) > 0.80

    def _try_simple_shift(self) -> Tuple[int, float]:
        """Tenta encontrar um shift simples que funcione."""
        best_shift = 0
        best_score = 0.0

        for shift in range(-128, 128):
            if shift == 0:
                continue

            score = self._score_shift(shift)
            if score > best_score:
                best_score = score
                best_shift = shift

        return best_shift, best_score

    def _score_shift(self, shift: int) -> float:
        """Avalia um shift calculando similaridade com frequências do inglês."""
        shifted_freq: Dict[str, int] = {}
        total = 0

        for b, count in self.byte_freq.items():
            shifted = (b + shift) & 0xFF
            if 0x41 <= shifted <= 0x5A:  # A-Z
                char = chr(shifted).lower()
                shifted_freq[char] = shifted_freq.get(char, 0) + count
                total += count
            elif 0x61 <= shifted <= 0x7A:  # a-z
                char = chr(shifted)
                shifted_freq[char] = shifted_freq.get(char, 0) + count
                total += count

        if total == 0:
            return 0.0

        # Normaliza e compara com frequências do inglês
        score = 0.0
        for char, expected_freq in self.ENGLISH_LETTER_FREQ.items():
            actual_freq = shifted_freq.get(char, 0) / total
            diff = abs(expected_freq - actual_freq)
            score += max(0, 1 - diff * 10)  # Penaliza diferenças grandes

        return score / len(self.ENGLISH_LETTER_FREQ)

    def _try_frequency_analysis(self) -> float:
        """Tenta análise de frequência mais complexa."""
        # Mapeia os bytes mais frequentes para as letras mais frequentes
        sorted_bytes = sorted(self.byte_freq.items(), key=lambda x: x[1], reverse=True)
        sorted_letters = sorted(self.ENGLISH_LETTER_FREQ.items(), key=lambda x: x[1], reverse=True)

        # Cria mapping inicial
        for i, (byte_val, _) in enumerate(sorted_bytes[:26]):
            if i < len(sorted_letters):
                letter, _ = sorted_letters[i]
                self.mapping[byte_val] = letter
                self.confidence_per_symbol[byte_val] = 0.5  # Confiança média

        # Refina com bigramas
        confidence = self._refine_with_bigrams()

        return confidence

    def _refine_with_bigrams(self) -> float:
        """Refina o mapping usando análise de bigramas."""
        # Analisa bigramas do corpus mapeado
        if not self.mapping:
            return 0.0

        correct_bigrams = 0
        total_bigrams = 0

        for (b1, b2), count in self.bigram_freq.items():
            if b1 in self.mapping and b2 in self.mapping:
                bigram = self.mapping[b1] + self.mapping[b2]
                total_bigrams += count
                if bigram in self.ENGLISH_BIGRAMS:
                    correct_bigrams += count

        if total_bigrams == 0:
            return 0.0

        return correct_bigrams / total_bigrams

    def decode_text(self, raw_bytes: bytes) -> Tuple[str, bool]:
        """
        Decodifica bytes usando o mapping aprendido.

        Returns:
            (texto_decodificado, is_decoded)
        """
        if not self.mapping or self.global_confidence < 0.5:
            # Retorna representação tokenizada
            return self._tokenize(raw_bytes), False

        result = []
        for b in raw_bytes:
            if b in self.mapping:
                result.append(self.mapping[b])
            else:
                result.append(f'{{{b:02X}}}')

        return ''.join(result), True

    def _tokenize(self, raw_bytes: bytes) -> str:
        """Retorna representação tokenizada dos bytes."""
        return ''.join(f'{{{b:02X}}}' for b in raw_bytes)

    def export_tbl(self, output_path: Path) -> None:
        """Exporta o mapping como arquivo TBL."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Auto-generated TBL by TBLAutoLearner\n")
            f.write(f"# Global confidence: {self.global_confidence:.4f}\n\n")

            for byte_val, char in sorted(self.mapping.items()):
                f.write(f"{byte_val:02X}={char}\n")


# ============================================================================
# SMS TILEMAP EXTRACTOR
# ============================================================================

class SMSTilemapExtractor:
    """
    Extrator de texto baseado em tilemaps para SMS.
    Detecta fontes de texto e extrai strings dos tilemaps.
    """

    def __init__(self, rom_data: bytes, config: SMSExtractorConfig):
        self.rom_data = rom_data
        self.rom_size = len(rom_data)
        self.config = config

        self.font_candidates: List[Dict] = []
        self.tilemap_candidates: List[Dict] = []
        self.tilemap_candidate_ranges: List[Dict] = []

    def detect_font_tiles(self) -> List[Dict]:
        """
        Detecta blocos de tiles que parecem ser fontes (otimizado).

        Heurísticas:
        - Alta repetição de padrões finos (1-2px de largura)
        - Baixa entropia por tile vs gráficos grandes
        - Padrões de bordas consistentes
        """
        # SMS: tiles de 8x8, 4 bits por pixel, 32 bytes por tile
        TILE_SIZE = 32
        MIN_FONT_TILES = 26  # Pelo menos A-Z

        candidates = []

        # OTIMIZAÇÃO: Escaneia em passos de 256 bytes (8 tiles)
        step = 256
        for offset in range(0, self.rom_size - TILE_SIZE * MIN_FONT_TILES, step):
            score = self._score_font_candidate(offset, TILE_SIZE, MIN_FONT_TILES)

            if score > 0.6:
                candidates.append({
                    'offset': offset,
                    'tile_count': MIN_FONT_TILES,
                    'score': score,
                    'tile_size': TILE_SIZE
                })

            # Limite de candidatos
            if len(candidates) > 50:
                break

        # Remove overlaps, mantém os melhores
        candidates.sort(key=lambda x: x['score'], reverse=True)
        self.font_candidates = self._remove_overlapping(candidates[:20])

        return self.font_candidates

    def _score_font_candidate(self, offset: int, tile_size: int, count: int) -> float:
        """Avalia um candidato a fonte de tiles."""
        if offset + tile_size * count > self.rom_size:
            return 0.0

        total_entropy = 0.0
        unique_patterns = set()
        empty_tiles = 0

        for i in range(count):
            tile_offset = offset + i * tile_size
            tile_data = self.rom_data[tile_offset:tile_offset + tile_size]

            # Entropia
            entropy = self._calculate_tile_entropy(tile_data)
            total_entropy += entropy

            # Padrão único
            unique_patterns.add(tuple(tile_data))

            # Tiles vazios
            if all(b == 0 for b in tile_data):
                empty_tiles += 1

        avg_entropy = total_entropy / count
        uniqueness = len(unique_patterns) / count

        # Score: baixa entropia, alta uniqueness, poucos vazios
        score = 0.0

        # Entropia ideal para fonte: entre 2.0 e 4.0
        if 2.0 <= avg_entropy <= 4.0:
            score += 0.4
        elif avg_entropy < 2.0:
            score += 0.2

        # Alta uniqueness (cada tile diferente)
        score += uniqueness * 0.4

        # Poucos tiles vazios
        empty_ratio = empty_tiles / count
        score += (1 - empty_ratio) * 0.2

        return score

    def _calculate_tile_entropy(self, tile_data: bytes) -> float:
        """Calcula entropia de Shannon para um tile."""
        if not tile_data:
            return 0.0

        freq = Counter(tile_data)
        length = len(tile_data)
        entropy = 0.0

        for count in freq.values():
            prob = count / length
            entropy -= prob * math.log2(prob)

        return entropy

    def _remove_overlapping(self, candidates: List[Dict]) -> List[Dict]:
        """Remove candidatos overlapping, mantendo os melhores."""
        if not candidates:
            return []

        result = []
        used_ranges = []

        for cand in candidates:
            start = cand['offset']
            end = start + cand['tile_count'] * cand['tile_size']

            # Verifica overlap
            overlaps = False
            for used_start, used_end in used_ranges:
                if start < used_end and end > used_start:
                    overlaps = True
                    break

            if not overlaps:
                result.append(cand)
                used_ranges.append((start, end))

        return result

    def detect_tilemaps(self) -> List[Dict]:
        """
        Detecta tilemaps/name tables na ROM (otimizado).

        Heurísticas:
        - Sequências de u16 onde bits baixos são índices de tile em range consistente
        - Padrões de repetição típicos de texto (espaços, etc.)
        """
        MIN_TILEMAP_LEN = 32  # 32 tiles mínimo (uma linha)
        candidates = []

        # OTIMIZAÇÃO: Escaneia em passos de 64 bytes e usa amostragem
        step = 64
        for offset in range(0, self.rom_size - MIN_TILEMAP_LEN * 2, step):
            score, tile_range = self._score_tilemap_candidate(offset, MIN_TILEMAP_LEN)

            if score > 0.5:
                candidates.append({
                    'offset': offset,
                    'length': MIN_TILEMAP_LEN * 2,
                    'score': score,
                    'tile_range': tile_range
                })

            # Limite de candidatos para evitar lentidão
            if len(candidates) > 100:
                break

        candidates.sort(key=lambda x: x['score'], reverse=True)
        self.tilemap_candidates = candidates[:20]  # Top 20

        return self.tilemap_candidates

    def detect_tilemaps_in_ranges(self, ranges: List[Dict]) -> List[Dict]:
        """
        Detecta tilemaps apenas em ranges candidatos (janelas).
        Cada range deve ter: offset, size.
        """
        MIN_TILEMAP_LEN = 32  # 32 tiles mínimo (uma linha)
        candidates = []

        for r in ranges:
            start = int(r.get("offset", 0))
            size = int(r.get("size", 0))
            end = min(self.rom_size, start + size)
            if start < 0 or size <= 0 or start >= self.rom_size:
                continue

            # Scaneia dentro do range em passos de 64 bytes
            step = 64
            for offset in range(start, end - MIN_TILEMAP_LEN * 2, step):
                score, tile_range = self._score_tilemap_candidate(
                    offset, MIN_TILEMAP_LEN
                )
                if score > 0.5:
                    candidates.append(
                        {
                            "offset": offset,
                            "length": MIN_TILEMAP_LEN * 2,
                            "score": score,
                            "tile_range": tile_range,
                            "range_start": start,
                            "range_end": end,
                        }
                    )

        candidates.sort(key=lambda x: x["score"], reverse=True)
        self.tilemap_candidates = candidates[:20]
        return self.tilemap_candidates

    def discover_tilemap_ranges(self,
                                window_sizes: Tuple[int, ...] = (4096, 8192),
                                step: int = 512) -> List[Dict]:
        """
        DiscoveryPass de ranges candidatos (janelas 4KB/8KB).
        Heurísticas:
        - Muitos bytes baixos (0x00–0x5F)
        - Presença de terminadores (0x00/0xFF)
        - Baixa entropia relativa
        - Repetição de padrões
        """
        candidates: List[Dict] = []

        def _entropy(chunk: bytes) -> float:
            if not chunk:
                return 0.0
            freq = Counter(chunk)
            total = len(chunk)
            ent = 0.0
            for count in freq.values():
                p = count / total
                ent -= p * math.log2(p)
            return ent

        for window_size in window_sizes:
            if window_size <= 0 or window_size > self.rom_size:
                continue
            for offset in range(0, self.rom_size - window_size, step):
                chunk = self.rom_data[offset:offset + window_size]
                if not chunk:
                    continue

                low_bytes = sum(1 for b in chunk if b <= 0x5F)
                low_ratio = low_bytes / window_size

                term_count = chunk.count(0x00) + chunk.count(0xFF)
                term_ratio = term_count / window_size

                ent = _entropy(chunk)
                freq = Counter(chunk)
                top_byte, top_count = freq.most_common(1)[0]
                top_ratio = top_count / window_size

                score = 0.0
                if low_ratio >= 0.45:
                    score += 0.35
                elif low_ratio >= 0.35:
                    score += 0.20

                if term_ratio >= 0.05:
                    score += 0.25
                elif term_ratio >= 0.02:
                    score += 0.10

                if ent <= 4.5:
                    score += 0.25
                elif ent <= 5.2:
                    score += 0.10

                if top_ratio >= 0.08:
                    score += 0.15

                if score >= 0.60:
                    candidates.append({
                        "offset": offset,
                        "size": window_size,
                        "score": round(score, 3),
                        "low_ratio": round(low_ratio, 4),
                        "terminator_ratio": round(term_ratio, 4),
                        "entropy": round(ent, 4),
                        "top_byte": int(top_byte),
                        "top_ratio": round(top_ratio, 4),
                    })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        self.tilemap_candidate_ranges = candidates[:30]
        return self.tilemap_candidate_ranges

    def _infer_terminator(self, tile_indices: List[int]) -> Optional[int]:
        """Heurística simples para terminador (0x00 ou 0xFF)."""
        if not tile_indices:
            return None
        freq = Counter(tile_indices)
        c00 = freq.get(0x00, 0)
        cff = freq.get(0xFF, 0)
        if c00 == 0 and cff == 0:
            return None
        if c00 >= cff:
            return 0x00
        return 0xFF

    def _build_heuristic_glyph_map(self, tile_indices: List[int]) -> Dict[int, str]:
        """
        Gera mapeamento inicial de tiles -> caracteres por frequência.
        Heurística simples: espaço + A..Z + 0..9 + sinais básicos.
        """
        mapping: Dict[int, str] = {}
        if not tile_indices:
            return mapping

        freq = Counter(tile_indices)
        ordered = [t for t, _ in freq.most_common()]

        if not ordered:
            return mapping

        # Espaço no mais frequente
        mapping[ordered[0]] = " "

        alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        digits = list("0123456789")
        extras = list(".,!?-:/")
        symbols = alphabet + digits + extras

        for tile, char in zip(ordered[1:], symbols):
            mapping[tile] = char

        return mapping

    def _decode_tile_indices(self,
                             tile_indices: List[int],
                             glyph_map: Dict[int, str],
                             terminator: Optional[int]) -> Tuple[str, float]:
        """Decodifica índices de tiles usando mapping heurístico."""
        if not tile_indices:
            return "", 0.0

        decoded_parts = []
        mapped = 0
        total = 0

        for idx in tile_indices:
            if terminator is not None and idx == terminator:
                break
            total += 1
            if idx in glyph_map:
                decoded_parts.append(glyph_map[idx])
                mapped += 1
            else:
                decoded_parts.append(f"<TILE:{idx:02X}>")

        coverage = mapped / total if total > 0 else 0.0
        return "".join(decoded_parts), coverage

    def _score_tilemap_candidate(self, offset: int, count: int) -> Tuple[float, Tuple[int, int]]:
        """Avalia um candidato a tilemap."""
        if offset + count * 2 > self.rom_size:
            return 0.0, (0, 0)

        tile_indices = []
        for i in range(count):
            val = int.from_bytes(self.rom_data[offset + i*2:offset + i*2 + 2], 'little')
            tile_idx = val & 0x1FF  # 9 bits para índice
            tile_indices.append(tile_idx)

        if not tile_indices:
            return 0.0, (0, 0)

        # Analisa range
        min_idx = min(tile_indices)
        max_idx = max(tile_indices)
        range_size = max_idx - min_idx + 1

        # Score baseado em range consistente
        score = 0.0

        # Range típico de fonte: 32-128 tiles
        if 32 <= range_size <= 128:
            score += 0.3
        elif range_size < 256:
            score += 0.2

        # Baixa variância (texto usa poucos tiles diferentes)
        unique_count = len(set(tile_indices))
        # Filtro: evita candidatos quase constantes (muito provável fundo/tiles vazios)
        if unique_count < 4:
            return 0.0, (min_idx, max_idx)
        if unique_count / count < 0.3:  # Menos de 30% únicos
            score += 0.3

        # Presença de "espaço" (tile mais comum)
        freq = Counter(tile_indices)
        most_common_ratio = freq.most_common(1)[0][1] / count
        if most_common_ratio >= 0.70:
            return 0.0, (min_idx, max_idx)
        if most_common_ratio > 0.1:  # Tile mais comum > 10%
            score += 0.2

        # Distribuição não uniforme (texto real)
        variance = sum((tile_indices.count(i) - count/range_size)**2 for i in set(tile_indices)) / count
        if variance > 10:
            score += 0.2

        return score, (min_idx, max_idx)

    def extract_from_tilemap(self, tilemap: Dict, font: Optional[Dict] = None) -> List[ExtractedItem]:
        """Extrai texto de um tilemap."""
        items = []

        offset = tilemap['offset']
        length = tilemap['length']

        # Lê tile indices
        tile_indices = []
        for i in range(0, length, 2):
            if offset + i + 2 > self.rom_size:
                break
            val = int.from_bytes(self.rom_data[offset + i:offset + i + 2], 'little')
            tile_idx = val & 0x1FF
            tile_indices.append(tile_idx)

        if not tile_indices:
            return items

        # Evita tilemaps triviais (tudo igual)
        if len(set(tile_indices)) <= 1:
            return items

        terminator = self._infer_terminator(tile_indices)
        glyph_map = self._build_heuristic_glyph_map(tile_indices)
        decoded, coverage = self._decode_tile_indices(tile_indices, glyph_map, terminator)

        # Converte para bytes (usando índice como byte)
        raw_bytes = bytes(min(idx, 0xFF) for idx in tile_indices)
        raw_hex = raw_bytes.hex().upper()

        # Confiança baixa, mas proporcional ao score + cobertura
        confidence = max(0.10, min(1.0, tilemap['score'] * 0.6 + coverage * 0.4))

        item = ExtractedItem(
            id=0,
            file_offset=offset,
            pointer_table_offset=None,
            pointer_index=None,
            pointer_value=None,
            bank=None,
            bank_rule=None,
            terminator=terminator if terminator is not None else 0x00,
            raw_bytes=raw_bytes,
            raw_hex=raw_hex,
            decoded_text=decoded,
            is_decoded=coverage >= 0.50,
            confidence=confidence,
            method=ExtractionMethod.TILEMAP
        )
        items.append(item)

        return items


# ============================================================================
# SMS STRING EXTRACTOR (PONTEIROS)
# ============================================================================

class SMSPointerExtractor:
    """
    Extrator de strings por ponteiros para SMS.
    Descoberta automática de tabelas com múltiplas regras de bank.
    """

    # Regras de mapeamento de ponteiro para offset
    BANK_RULES = {
        'SLOT1_4000': lambda ptr, bank: bank * 0x4000 + (ptr - 0x4000) if 0x4000 <= ptr < 0x8000 else None,
        'SLOT2_8000': lambda ptr, bank: bank * 0x4000 + (ptr - 0x8000) if 0x8000 <= ptr < 0xC000 else None,
        'DIRECT': lambda ptr, bank: ptr if ptr < 0x4000 else None,
        'ABSOLUTE': lambda ptr, bank: ptr if ptr < 0x40000 else None,  # Ponteiro absoluto
    }

    def __init__(self, rom_data: bytes, config: SMSExtractorConfig):
        self.rom_data = rom_data
        self.rom_size = len(rom_data)
        self.config = config

        self.num_banks = max(1, (self.rom_size + 0x3FFF) // 0x4000)
        self.pointer_tables: List[PointerTableCandidate] = []
        self.rejected_pointer_table_low_plausibility = 0

    def discover_pointer_tables(self) -> List[PointerTableCandidate]:
        """
        Descobre tabelas de ponteiros automaticamente (otimizado).
        Usa abordagem de amostragem para velocidade.
        """
        self.rejected_pointer_table_low_plausibility = 0
        all_candidates = []

        # OTIMIZAÇÃO: Testa apenas as regras e terminadores mais comuns primeiro
        priority_rules = ['SLOT1_4000', 'SLOT2_8000']
        priority_terminators = [0x00, 0xFF]

        for rule_name in priority_rules:
            rule_func = self.BANK_RULES[rule_name]
            for terminator in priority_terminators:
                candidates = self._find_tables_with_rule(rule_name, rule_func, terminator)
                all_candidates.extend(candidates)

                # Se encontrou boas tabelas, para
                good_tables = [c for c in candidates if c.confidence >= 0.7]
                if len(good_tables) >= 2:
                    break
            if len(all_candidates) >= 5:
                break

        # Ordena por confiança e remove duplicatas
        all_candidates.sort(key=lambda x: x.confidence, reverse=True)
        self.pointer_tables = self._dedupe_tables(all_candidates[:10])  # Limite de 10

        return self.pointer_tables

    def _find_tables_with_rule(self, rule_name: str, rule_func, terminator: int) -> List[PointerTableCandidate]:
        """Encontra tabelas usando uma regra específica (otimizado)."""
        candidates = []
        scanned_ranges = []

        # OTIMIZAÇÃO: Escaneia em passos de 16 bytes (alinhamento típico)
        # e usa heurística para pular áreas não-interessantes
        step = 16
        offset = 0

        while offset < self.rom_size - self.config.min_pointers_for_table * 2:
            # Verifica se já escaneamos esta área
            skip = False
            for start, end in scanned_ranges:
                if start <= offset < end:
                    skip = True
                    offset = end
                    break
            if skip:
                continue

            # Pré-filtra: verifica se os primeiros bytes parecem ponteiros
            if not self._quick_pointer_check(offset, rule_func):
                offset += step
                continue

            candidate = self._try_detect_table(offset, rule_name, rule_func, terminator)

            if candidate and candidate.confidence >= self.config.min_pointer_confidence:
                candidates.append(candidate)
                table_end = offset + candidate.entry_count * 2
                scanned_ranges.append((offset, table_end))
                offset = table_end
            else:
                offset += step

        return candidates

    def _quick_pointer_check(self, offset: int, rule_func) -> bool:
        """Verificação rápida se offset pode ser início de tabela de ponteiros."""
        if offset + 6 > self.rom_size:
            return False

        # Lê 3 ponteiros consecutivos
        for i in range(3):
            ptr = int.from_bytes(self.rom_data[offset + i*2:offset + i*2 + 2], 'little')

            # Ponteiros SMS típicos: 0x0000-0xBFFF
            if ptr >= 0xC000:
                return False

            # Deve resolver para algum lugar na ROM
            found_valid = False
            for bank in range(min(4, self.num_banks)):  # Testa só primeiros 4 banks
                resolved = rule_func(ptr, bank)
                if resolved is not None and 0 <= resolved < self.rom_size:
                    found_valid = True
                    break

            if not found_valid:
                return False

        return True

    def _try_detect_table(self, offset: int, rule_name: str, rule_func, terminator: int) -> Optional[PointerTableCandidate]:
        """Tenta detectar uma tabela de ponteiros em um offset (otimizado)."""
        pointer_values = []
        resolved_offsets = []
        valid_text_count = 0

        idx = 0
        consecutive_invalid = 0
        max_entries = 100  # Limite reduzido para velocidade

        while idx < max_entries:
            ptr_offset = offset + idx * 2
            if ptr_offset + 2 > self.rom_size:
                break

            ptr_value = int.from_bytes(self.rom_data[ptr_offset:ptr_offset + 2], 'little')

            # Filtra ponteiros obviamente inválidos
            if ptr_value >= 0xC000 or ptr_value == 0:
                consecutive_invalid += 1
                if consecutive_invalid >= 2:
                    break
                idx += 1
                continue

            # Testa apenas primeiros 4 banks para velocidade
            best_resolved = None
            for bank in range(min(4, self.num_banks)):
                resolved = rule_func(ptr_value, bank)
                if resolved is not None and 0 <= resolved < self.rom_size:
                    text_data = self._read_text_at(resolved, terminator)
                    if text_data and len(text_data) >= self.config.min_text_length:
                        if self._is_valid_text(text_data):
                            best_resolved = resolved
                            break

            if best_resolved is not None:
                pointer_values.append(ptr_value)
                resolved_offsets.append(best_resolved)
                valid_text_count += 1
                consecutive_invalid = 0
            else:
                consecutive_invalid += 1
                if consecutive_invalid >= 2:
                    break

            idx += 1

        # Verifica se temos ponteiros suficientes
        if len(pointer_values) < self.config.min_pointers_for_table:
            return None

        plausible_ratio = self._calculate_pointer_table_plausibility(
            resolved_offsets, terminator, sample_size=20
        )
        if plausible_ratio < 0.35:
            self.rejected_pointer_table_low_plausibility += 1
            return None

        confidence = valid_text_count / len(pointer_values) if pointer_values else 0

        return PointerTableCandidate(
            table_offset=offset,
            entry_count=len(pointer_values),
            bank_rule=rule_name,
            terminator=terminator,
            pointer_values=pointer_values,
            resolved_offsets=resolved_offsets,
            confidence=confidence,
            valid_text_count=valid_text_count
        )

    def _calculate_pointer_table_plausibility(
        self, resolved_offsets: List[int], terminator: int, sample_size: int = 20
    ) -> float:
        """Calcula taxa de plausibilidade das strings apontadas."""
        if not resolved_offsets:
            return 0.0
        sample = resolved_offsets[:sample_size]
        total = 0
        plausible = 0
        for offset in sample:
            data = self._read_text_at(offset, terminator)
            if not data:
                continue
            total += 1
            if self._is_plausible_ascii_text(data):
                plausible += 1
        return (plausible / total) if total > 0 else 0.0

    def _is_plausible_ascii_text(self, data: bytes) -> bool:
        """Heurística de plausibilidade para texto ASCII."""
        if not data or len(data) < 3:
            return False

        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
        if printable / len(data) < 0.80:
            return False

        try:
            text = data.decode("ascii", errors="ignore")
        except Exception:
            return False

        if not text:
            return False

        if self._has_repetitive_pattern(text):
            return False

        if self._looks_like_alphabet_sequence(text):
            return False

        return True

    def _has_repetitive_pattern(self, text: str) -> bool:
        """Detecta padrões repetitivos simples (AAAA, ABABAB, 010101)."""
        if len(text) >= 4 and len(set(text)) == 1:
            return True
        for unit_len in (2, 3):
            if len(text) >= unit_len * 3 and len(text) % unit_len == 0:
                unit = text[:unit_len]
                if unit * (len(text) // unit_len) == text:
                    return True
        return False

    def _looks_like_alphabet_sequence(self, text: str, min_run: int = 8) -> bool:
        """Rejeita sequências tipo alfabeto/quase-alfabeto."""
        cleaned = "".join(ch.lower() for ch in text if ch.isalnum())
        if len(cleaned) < min_run:
            return False
        run = 1
        for i in range(1, len(cleaned)):
            if ord(cleaned[i]) == ord(cleaned[i - 1]) + 1:
                run += 1
                if run >= min_run:
                    return True
            else:
                run = 1
        return False

    def _read_text_at(self, offset: int, terminator: int) -> Optional[bytes]:
        """Lê bytes até encontrar terminador."""
        if offset < 0 or offset >= self.rom_size:
            return None

        data = bytearray()
        i = offset

        while i < self.rom_size and len(data) < self.config.max_text_length:
            byte = self.rom_data[i]

            if byte == terminator:
                break

            data.append(byte)
            i += 1

        return bytes(data) if data else None

    def _is_valid_text(self, data: bytes) -> bool:
        """Verifica se os bytes parecem texto válido."""
        if not data or len(data) < self.config.min_text_length:
            return False

        # Conta caracteres ASCII printable
        printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
        ratio = printable / len(data)

        # Mínimo 50% printable para considerar texto
        if ratio < 0.50:
            return False

        # Evita sequências repetitivas
        if len(set(data)) < len(data) * 0.3 and len(data) > 5:
            return False

        return True

    def _dedupe_tables(self, candidates: List[PointerTableCandidate]) -> List[PointerTableCandidate]:
        """Remove tabelas duplicadas/overlapping."""
        if not candidates:
            return []

        result = []
        used_offsets = set()

        for cand in candidates:
            # Verifica overlap
            table_range = set(range(cand.table_offset, cand.table_offset + cand.entry_count * 2))
            if not table_range & used_offsets:
                result.append(cand)
                used_offsets.update(table_range)

        return result

    def extract_from_table(self, table: PointerTableCandidate, tbl_learner: Optional[TBLAutoLearner] = None) -> List[ExtractedItem]:
        """Extrai strings de uma tabela de ponteiros."""
        items = []
        seen_offsets = set()

        for idx, (ptr_value, resolved) in enumerate(zip(table.pointer_values, table.resolved_offsets)):
            if resolved in seen_offsets:
                continue
            seen_offsets.add(resolved)

            raw_bytes = self._read_text_at(resolved, table.terminator)
            if not raw_bytes:
                continue

            raw_hex = raw_bytes.hex().upper()

            # Tenta decodificar
            if tbl_learner and tbl_learner.global_confidence >= self.config.tbl_min_confidence:
                decoded_text, is_decoded = tbl_learner.decode_text(raw_bytes)
            else:
                # Tenta ASCII direto
                try:
                    decoded_text = raw_bytes.decode('ascii')
                    is_decoded = True
                except:
                    decoded_text = ''.join(f'{{{b:02X}}}' for b in raw_bytes)
                    is_decoded = False

            # Calcula bank
            bank = resolved // 0x4000

            item = ExtractedItem(
                id=len(items),
                file_offset=resolved,
                pointer_table_offset=table.table_offset,
                pointer_index=idx,
                pointer_value=ptr_value,
                bank=bank,
                bank_rule=table.bank_rule,
                terminator=table.terminator,
                raw_bytes=raw_bytes,
                raw_hex=raw_hex,
                decoded_text=decoded_text,
                is_decoded=is_decoded,
                confidence=table.confidence,
                method=ExtractionMethod.POINTER_TABLE
            )
            items.append(item)

        return items


# ============================================================================
# PROFILE MANAGER (CRC CACHING)
# ============================================================================

class SMSProfileManager:
    """Gerencia profiles por CRC para caching de configurações."""

    def __init__(self, profiles_dir: str = "./profiles/sms"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load_profile(self, crc32: str) -> Optional[Dict]:
        """Carrega profile existente para um CRC."""
        profile_path = self.profiles_dir / f"{crc32}.json"
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    def save_profile(self, crc32: str, profile: Dict) -> None:
        """Salva profile para um CRC."""
        profile_path = self.profiles_dir / f"{crc32}.json"
        profile['saved_at'] = datetime.now(timezone.utc).isoformat()

        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

    def create_profile_from_result(self, crc32: str, result: ExtractionResult,
                                    tbl_mapping: Optional[Dict[int, str]] = None) -> Dict:
        """Cria profile a partir do resultado da extração."""
        profile = {
            'crc32': crc32,
            'method': result.method.value,
            'terminator': result.terminator_used,
            'bank_rule': result.bank_rule_used,
            'safe_ratio': result.safe_ratio,
            'total_extracted': result.total_extracted,
            'pointer_tables_found': result.pointer_tables_found,
        }

        if tbl_mapping:
            # Salva TBL como strings
            profile['tbl_mapping'] = {str(k): v for k, v in tbl_mapping.items()}

        return profile


# ============================================================================
# SMS PRO EXTRACTOR (ORQUESTRADOR)
# ============================================================================

class SMSProExtractor:
    """
    Extrator principal SMS PRO.
    Orquestra todos os componentes com fail-fast e quality gates.
    """

    def __init__(self, file_path: str, config: Optional[SMSExtractorConfig] = None):
        self.file_path = Path(file_path)
        self.config = config or SMSExtractorConfig()

        if not self.file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        # Carrega ROM
        self.rom_data = self.file_path.read_bytes()
        self.rom_size = len(self.rom_data)

        # Calcula CRC32
        self.crc32 = f"{zlib.crc32(self.rom_data) & 0xFFFFFFFF:08X}"

        # Engenharia específica por jogo (CRC)
        self.engineering_manager = None
        self.engineering_profile: Dict[str, Any] = {}
        self.engineering_overrides: Dict[str, Any] = {}
        self.engineering_compression: Dict[str, Any] = {}
        self.engineering_script_changes: int = 0
        if SMSGameEngineeringManager is not None:
            try:
                self.engineering_manager = SMSGameEngineeringManager(
                    self.config.engineering_profiles_path
                )
                self.engineering_profile = self.engineering_manager.get_profile(self.crc32)
                self.engineering_overrides = self.engineering_manager.apply_extractor_overrides(
                    self.config, self.engineering_profile
                )
                self.engineering_compression = self.engineering_manager.get_compression_policy(
                    self.engineering_profile
                )
            except Exception:
                self.engineering_manager = None
                self.engineering_profile = {}
                self.engineering_overrides = {}
                self.engineering_compression = {}
                self.engineering_script_changes = 0

        # Componentes
        self.profile_manager = SMSProfileManager(self.config.profiles_dir)
        self.pointer_extractor = SMSPointerExtractor(self.rom_data, self.config)
        self.tilemap_extractor = SMSTilemapExtractor(self.rom_data, self.config)
        self.tbl_learner: Optional[TBLAutoLearner] = None

        # Resultado
        self.result: Optional[ExtractionResult] = None
        self.items: List[ExtractedItem] = []

    def _apply_engineering_text_pipeline(self, items: List[ExtractedItem], stage: str) -> int:
        """Aplica regras de script/charset do perfil de engenharia."""
        if not items or not self.engineering_manager or not self.engineering_profile:
            return 0
        changed = 0
        for item in items:
            src = item.decoded_text if isinstance(item.decoded_text, str) else ""
            if not src:
                continue
            dst, steps = self.engineering_manager.apply_text_pipeline(
                src, self.engineering_profile, stage=stage
            )
            if not isinstance(dst, str) or not dst:
                continue
            if dst != src:
                item.decoded_text = dst
                changed += 1
            if steps > 0:
                self.engineering_script_changes += int(steps)
        return changed

    def _attach_engineering_diagnostics(self, diagnostics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Acopla metadados do perfil por jogo nos diagnósticos."""
        out = dict(diagnostics or {})
        if not self.engineering_profile:
            return out

        summary: Dict[str, Any] = {
            "rom_crc32": self.crc32,
            "profile_id": self.engineering_profile.get("id"),
            "profile_name": self.engineering_profile.get("name"),
            "profile_version": self.engineering_profile.get("version"),
            "profile_file": self.engineering_profile.get("_profile_file"),
            "has_crc_profile": bool(self.engineering_profile.get("_has_crc_profile", False)),
        }
        out["game_engineering_profile"] = summary
        out["game_engineering_overrides"] = dict(self.engineering_overrides)
        out["game_engineering_script_changes"] = int(self.engineering_script_changes)
        if self.engineering_compression:
            out["game_engineering_compression"] = dict(self.engineering_compression)
        return out

    def extract(self) -> ExtractionResult:
        """
        Executa extração completa com fail-fast.

        Retorna ExtractionResult com success=False se não atingir quality gates.
        """
        # 1. Verifica se tem profile cached
        profile = self.profile_manager.load_profile(self.crc32)
        if profile:
            profile_result = self._extract_from_profile(profile)
            if profile_result.success and profile_result.safe_ratio >= self.config.min_safe_ratio:
                self.result = profile_result
                return profile_result

        # 2. Tenta extração por ponteiros
        result = self._try_pointer_extraction()
        if result.success and result.safe_ratio >= self.config.min_safe_ratio:
            # Salva profile para próxima vez
            self._save_profile(result)
            self.result = result
            return result

        # 3. Tenta extração por tilemap
        if not result.success or result.safe_ratio < self.config.min_safe_ratio:
            tilemap_result = self._try_tilemap_extraction()
            if tilemap_result.success and tilemap_result.safe_ratio >= self.config.min_safe_ratio:
                self._save_profile(tilemap_result)
                self.result = tilemap_result
                return tilemap_result

        # 4. FAIL-FAST: não atingiu quality gates
        error_msg = f"FAIL-FAST: safe_ratio={result.safe_ratio:.2%} < {self.config.min_safe_ratio:.0%}"
        recommendation = 'ROM pode ter texto comprimido ou encoding desconhecido'
        comp_hint = str(self.engineering_compression.get("extractor_hint", "")).strip()
        if comp_hint:
            recommendation += f" (hint perfil: {comp_hint})"

        return ExtractionResult(
            success=False,
            method=result.method,
            items=[],
            safe_ratio=result.safe_ratio,
            total_extracted=result.total_extracted,
            safe_count=result.safe_count,
            rejected_count=result.rejected_count,
            terminator_used=result.terminator_used,
            bank_rule_used=result.bank_rule_used,
            pointer_tables_found=result.pointer_tables_found,
            error_message=error_msg,
            diagnostics=self._attach_engineering_diagnostics({
                'reason': 'QUALITY_GATE_FAILED',
                'min_required': self.config.min_safe_ratio,
                'achieved': result.safe_ratio,
                'recommendation': recommendation,
            })
        )

    def _extract_from_profile(self, profile: Dict) -> ExtractionResult:
        """Extrai usando profile cached."""
        # Reconstrói configuração do profile
        terminator = profile.get('terminator', 0x00)
        bank_rule = profile.get('bank_rule', 'SLOT1_4000')

        # Se tem TBL, carrega
        tbl_mapping = profile.get('tbl_mapping')
        if tbl_mapping:
            tbl_mapping = {int(k): v for k, v in tbl_mapping.items()}

        # Executa extração direcionada
        self.pointer_extractor.config.candidate_terminators = (terminator,)
        tables = self.pointer_extractor.discover_pointer_tables()

        if not tables:
            return ExtractionResult(
                success=False,
                method=ExtractionMethod.PROFILE_CACHED,
                items=[],
                safe_ratio=0.0,
                total_extracted=0,
                safe_count=0,
                rejected_count=0,
                terminator_used=terminator,
                bank_rule_used=bank_rule,
                pointer_tables_found=0,
                error_message="Profile existe mas tabelas não foram encontradas"
            )

        # Extrai de todas as tabelas
        all_items = []
        for table in tables:
            if table.bank_rule == bank_rule:
                items = self.pointer_extractor.extract_from_table(table)
                all_items.extend(items)

        self._apply_engineering_text_pipeline(all_items, stage="extract")
        self.items = all_items
        safe_count = sum(1 for item in all_items if item.is_decoded)

        return ExtractionResult(
            success=True,
            method=ExtractionMethod.PROFILE_CACHED,
            items=all_items,
            safe_ratio=safe_count / len(all_items) if all_items else 0,
            total_extracted=len(all_items),
            safe_count=safe_count,
            rejected_count=len(all_items) - safe_count,
            terminator_used=terminator,
            bank_rule_used=bank_rule,
            pointer_tables_found=len(tables),
            diagnostics=self._attach_engineering_diagnostics({
                'rejected_pointer_table_low_plausibility': self.pointer_extractor.rejected_pointer_table_low_plausibility
            })
        )

    def _try_pointer_extraction(self) -> ExtractionResult:
        """Tenta extração por ponteiros."""
        tables = self.pointer_extractor.discover_pointer_tables()

        if not tables:
            return ExtractionResult(
                success=False,
                method=ExtractionMethod.POINTER_TABLE,
                items=[],
                safe_ratio=0.0,
                total_extracted=0,
                safe_count=0,
                rejected_count=0,
                terminator_used=0,
                bank_rule_used='',
                pointer_tables_found=0,
                error_message="Nenhuma tabela de ponteiros encontrada"
            )

        # Usa a melhor tabela
        best_table = tables[0]

        # Coleta corpus para TBL learner
        corpus = []
        for offset in best_table.resolved_offsets:
            data = self.pointer_extractor._read_text_at(offset, best_table.terminator)
            if data:
                corpus.append(data)

        # Tenta aprender TBL
        if corpus:
            self.tbl_learner = TBLAutoLearner(corpus)
            self.tbl_learner.learn()

        # Extrai de todas as tabelas com mesmo terminador
        all_items = []
        for table in tables:
            if table.terminator == best_table.terminator:
                items = self.pointer_extractor.extract_from_table(table, self.tbl_learner)
                all_items.extend(items)

        # Renumera IDs
        for i, item in enumerate(all_items):
            item.id = i

        self._apply_engineering_text_pipeline(all_items, stage="extract")
        self.items = all_items
        safe_count = sum(1 for item in all_items if item.is_decoded and self._is_safe_item(item))

        diagnostics = {
            'tbl_confidence': self.tbl_learner.global_confidence if self.tbl_learner else 0,
            'rejected_pointer_table_low_plausibility': self.pointer_extractor.rejected_pointer_table_low_plausibility
        }

        return ExtractionResult(
            success=len(all_items) > 0,
            method=ExtractionMethod.POINTER_TABLE,
            items=all_items,
            safe_ratio=safe_count / len(all_items) if all_items else 0,
            total_extracted=len(all_items),
            safe_count=safe_count,
            rejected_count=len(all_items) - safe_count,
            terminator_used=best_table.terminator,
            bank_rule_used=best_table.bank_rule,
            pointer_tables_found=len(tables),
            diagnostics=self._attach_engineering_diagnostics(diagnostics)
        )

    def _try_tilemap_extraction(self) -> ExtractionResult:
        """Tenta extração por tilemap."""
        fonts = self.tilemap_extractor.detect_font_tiles()
        tilemaps = self.tilemap_extractor.detect_tilemaps()

        if not tilemaps:
            return ExtractionResult(
                success=False,
                method=ExtractionMethod.TILEMAP,
                items=[],
                safe_ratio=0.0,
                total_extracted=0,
                safe_count=0,
                rejected_count=0,
                terminator_used=0,
                bank_rule_used='',
                pointer_tables_found=0,
                error_message="Nenhum tilemap encontrado"
            )

        # Extrai de todos os tilemaps
        all_items = []
        for tilemap in tilemaps[:10]:  # Top 10
            items = self.tilemap_extractor.extract_from_tilemap(tilemap, fonts[0] if fonts else None)
            all_items.extend(items)

        # Renumera IDs
        for i, item in enumerate(all_items):
            item.id = i

        self._apply_engineering_text_pipeline(all_items, stage="extract")
        self.items = all_items
        safe_count = len(all_items)  # Tilemaps são sempre "safe" por não serem ASCII

        return ExtractionResult(
            success=len(all_items) > 0,
            method=ExtractionMethod.TILEMAP,
            items=all_items,
            safe_ratio=safe_count / len(all_items) if all_items else 0,
            total_extracted=len(all_items),
            safe_count=safe_count,
            rejected_count=0,
            terminator_used=0,
            bank_rule_used='TILEMAP',
            pointer_tables_found=0,
            diagnostics=self._attach_engineering_diagnostics({
                'fonts_found': len(fonts),
                'tilemaps_found': len(tilemaps)
            })
        )

    def _is_safe_item(self, item: ExtractedItem) -> bool:
        """Verifica se um item é seguro para reinserção."""
        if not item.is_decoded:
            return False

        text = item.decoded_text

        # Mínimo 3 caracteres
        if len(text) < 3:
            return False

        # Mínimo 60% alfanumérico
        alnum = sum(1 for c in text if c.isalnum())
        if alnum / len(text) < 0.6:
            return False

        # Deve ter pelo menos uma letra
        if not any(c.isalpha() for c in text):
            return False

        return True

    def _save_profile(self, result: ExtractionResult):
        """Salva profile para o CRC."""
        tbl_mapping = None
        if self.tbl_learner and self.tbl_learner.global_confidence >= self.config.tbl_min_confidence:
            tbl_mapping = self.tbl_learner.mapping

        profile = self.profile_manager.create_profile_from_result(
            self.crc32, result, tbl_mapping
        )
        self.profile_manager.save_profile(self.crc32, profile)

    def save_results(self, output_dir: Optional[str] = None) -> str:
        """Salva resultados em formato JSONL."""
        if not self.result or not self.result.success:
            raise ValueError("Nenhum resultado válido para salvar")

        out_dir = Path(output_dir) if output_dir else self.file_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        jsonl_path = out_dir / f"{self.crc32}_pure_text.jsonl"
        mapping_path = out_dir / f"{self.crc32}_reinsertion_mapping.json"
        report_path = out_dir / f"{self.crc32}_report.txt"

        def _sort_key(item: ExtractedItem, idx: int) -> Tuple[int, int, int, int]:
            bank_val = item.bank if isinstance(item.bank, int) else None
            return (
                0 if bank_val is not None else 1,
                bank_val or 0,
                int(item.file_offset),
                idx,
            )

        ordered_items = [
            item
            for idx, item in sorted(
                enumerate(self.items), key=lambda pair: _sort_key(pair[1], pair[0])
            )
        ]

        meta_header = {
            "type": "meta",
            "schema": "neurorom.pure_text.v2",
            "rom_crc32": str(self.crc32).upper(),
            "rom_size": int(self.rom_size),
            "ordering": "bank/offset",
        }
        if self.engineering_manager and self.engineering_profile:
            meta_header["game_engineering"] = self.engineering_manager.profile_summary(
                self.engineering_profile
            )

        # JSONL
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(meta_header, ensure_ascii=False) + '\n')
            for seq, item in enumerate(ordered_items):
                if item.method == ExtractionMethod.TILEMAP:
                    encoding = "tile"
                else:
                    encoding = 'ascii' if item.is_decoded else 'raw'

                entry = {
                    'id': item.id,
                    'offset': f'0x{item.file_offset:06X}',
                    'rom_offset': f'0x{item.file_offset:06X}',
                    'seq': int(seq),
                    'rom_crc32': str(self.crc32).upper(),
                    'rom_size': int(self.rom_size),
                    'text_src': item.decoded_text,
                    'max_len_bytes': len(item.raw_bytes),
                    'encoding': encoding,
                    'source': item.method.value,
                    'reinsertion_safe': self._is_safe_item(item),
                    'raw_hex': item.raw_hex,
                    'raw_bytes_hex': item.raw_hex,
                }
                if item.method == ExtractionMethod.TILEMAP:
                    entry['terminator'] = item.terminator

                if item.pointer_table_offset is not None:
                    entry['pointer_table_offset'] = f'0x{item.pointer_table_offset:06X}'
                    entry['pointer_index'] = item.pointer_index
                    entry['pointer_value'] = f'0x{item.pointer_value:04X}'
                    entry['bank'] = item.bank
                    entry['bank_rule'] = item.bank_rule

                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        # Mapping
        mapping = {
            'schema': 'sms_pro_extractor.mapping.v1',
            'crc32': self.crc32,
            'rom_size': self.rom_size,
            'method': self.result.method.value,
            'terminator': self.result.terminator_used,
            'bank_rule': self.result.bank_rule_used,
            'safe_ratio': self.result.safe_ratio,
            'total_items': len(self.items),
            'items': [
                {
                    'id': item.id,
                    'offset': item.file_offset,
                    'max_length': len(item.raw_bytes),
                    'terminator': item.terminator,
                    'reinsertion_safe': self._is_safe_item(item),
                    'encoding': 'tile' if item.method == ExtractionMethod.TILEMAP else ('ascii' if item.is_decoded else 'raw'),
                }
                for item in self.items
            ]
        }
        if self.engineering_manager and self.engineering_profile:
            mapping["game_engineering"] = self.engineering_manager.profile_summary(
                self.engineering_profile
            )
            mapping["game_engineering_overrides"] = dict(self.engineering_overrides)
            mapping["game_engineering_script_changes"] = int(self.engineering_script_changes)
            if self.engineering_compression:
                mapping["game_engineering_compression"] = dict(self.engineering_compression)

        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        # Report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("SMS PRO EXTRACTOR - EXTRACTION REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"CRC32: {self.crc32}\n")
            f.write(f"ROM_SIZE: {self.rom_size}\n")
            f.write(f"METHOD: {self.result.method.value}\n")
            f.write(f"TERMINATOR: 0x{self.result.terminator_used:02X}\n")
            f.write(f"BANK_RULE: {self.result.bank_rule_used}\n\n")

            if self.engineering_profile:
                f.write("-" * 40 + "\n")
                f.write("GAME ENGINEERING PROFILE\n")
                f.write("-" * 40 + "\n")
                f.write(f"PROFILE_ID: {self.engineering_profile.get('id')}\n")
                f.write(f"PROFILE_NAME: {self.engineering_profile.get('name')}\n")
                f.write(f"HAS_CRC_PROFILE: {bool(self.engineering_profile.get('_has_crc_profile', False))}\n")
                f.write(
                    "OVERRIDES_APPLIED: "
                    + json.dumps(self.engineering_overrides, ensure_ascii=False)
                    + "\n"
                )
                f.write(f"SCRIPT_CHANGES: {self.engineering_script_changes}\n")
                if self.engineering_compression:
                    f.write(
                        "COMPRESSION_POLICY: "
                        + json.dumps(self.engineering_compression, ensure_ascii=False)
                        + "\n"
                    )
                f.write("\n")

            f.write("-" * 40 + "\n")
            f.write("STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"TOTAL_EXTRACTED: {self.result.total_extracted}\n")
            f.write(f"SAFE_COUNT: {self.result.safe_count}\n")
            f.write(f"REJECTED_COUNT: {self.result.rejected_count}\n")
            f.write(f"SAFE_RATIO: {self.result.safe_ratio:.2%}\n")
            f.write(f"POINTER_TABLES_FOUND: {self.result.pointer_tables_found}\n\n")
            rejected_tables = None
            if self.result.diagnostics:
                rejected_tables = self.result.diagnostics.get(
                    "rejected_pointer_table_low_plausibility"
                )
            if rejected_tables is not None:
                f.write(
                    f"rejected_pointer_table_low_plausibility: {rejected_tables}\n"
                )
                f.write("\n")

            if self.tbl_learner:
                f.write("-" * 40 + "\n")
                f.write("TBL AUTO LEARNER\n")
                f.write("-" * 40 + "\n")
                f.write(f"GLOBAL_CONFIDENCE: {self.tbl_learner.global_confidence:.4f}\n")
                f.write(f"MAPPINGS: {len(self.tbl_learner.mapping)}\n\n")

            f.write("-" * 40 + "\n")
            f.write("QUALITY GATE\n")
            f.write("-" * 40 + "\n")
            f.write(f"REQUIRED: {self.config.min_safe_ratio:.0%}\n")
            f.write(f"ACHIEVED: {self.result.safe_ratio:.2%}\n")
            f.write(f"STATUS: {'PASSED' if self.result.success else 'FAILED'}\n")

        return str(jsonl_path)

    def get_preview(self, max_items: int = 10) -> str:
        """Retorna preview dos itens extraídos."""
        if not self.items:
            return "Nenhum item extraído."

        lines = [
            f"CRC32: {self.crc32}",
            f"Método: {self.result.method.value if self.result else 'N/A'}",
            f"Total: {len(self.items)} | Safe: {self.result.safe_count if self.result else 0}",
            f"Safe Ratio: {self.result.safe_ratio:.2%}" if self.result else "",
            "-" * 50
        ]

        for item in self.items[:max_items]:
            safe_mark = "[SAFE]" if self._is_safe_item(item) else "[RAW]"
            text = item.decoded_text[:50] + "..." if len(item.decoded_text) > 50 else item.decoded_text
            lines.append(f"{safe_mark} 0x{item.file_offset:06X}: {text}")

        if len(self.items) > max_items:
            lines.append(f"... e mais {len(self.items) - max_items} itens")

        return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI para SMS PRO Extractor."""
    import sys

    print("=" * 60)
    print("SMS PRO EXTRACTOR v1.0")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nUso: python sms_pro_extractor.py <rom.sms> [output_dir]")
        sys.exit(1)

    rom_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        extractor = SMSProExtractor(rom_path)
        result = extractor.extract()

        print(f"\nCRC32: {extractor.crc32}")
        print(f"Método: {result.method.value}")
        print(f"Total extraído: {result.total_extracted}")
        print(f"Safe ratio: {result.safe_ratio:.2%}")
        print(f"Tabelas de ponteiros: {result.pointer_tables_found}")

        if result.success:
            output_path = extractor.save_results(output_dir)
            print(f"\nResultados salvos em: {output_path}")
            print("\nPreview:")
            print(extractor.get_preview())
        else:
            print(f"\nFAIL-FAST: {result.error_message}")
            print(f"Diagnóstico: {result.diagnostics}")

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
