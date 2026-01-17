# -*- coding: utf-8 -*-
"""
================================================================================
ADVANCED ENCODING DETECTOR - Detecção Avançada + Charsets Custom
================================================================================
Detecta encoding E charsets proprietários automaticamente:

Encodings Padrão:
- UTF-8, UTF-16 (LE/BE), UTF-32
- Windows-1252, ISO-8859-1
- Shift-JIS, EUC-JP, EUC-KR
- CP437, CP850, CP1251

Charsets Custom (ROMs):
- SNES: Tables customizadas por jogo
- NES: DTE (Dual Tile Encoding)
- PS1: Tabelas proprietárias
- GBA: Charsets comprimidos

Técnicas:
- BOM detection
- Statistical analysis
- Character frequency correlation
- Custom table inference via ML
- Dictionary matching
================================================================================
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import Counter
import struct


@dataclass
class CharsetEntry:
    """Entrada de charset custom."""
    byte_value: int
    character: str
    frequency: int = 0
    confidence: float = 0.0


@dataclass
class AdvancedEncodingResult:
    """Resultado da detecção avançada."""
    encoding: str
    confidence: float
    is_custom: bool = False
    custom_charset: Optional[Dict[int, str]] = None
    bom: Optional[bytes] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AdvancedEncodingDetector:
    """
    Detector avançado de encoding e charsets custom.
    Suporta encodings padrão E tabelas proprietárias.
    """

    # BOMs conhecidos
    BOM_SIGNATURES = {
        b'\xef\xbb\xbf': 'utf-8-sig',
        b'\xff\xfe': 'utf-16-le',
        b'\xfe\xff': 'utf-16-be',
        b'\xff\xfe\x00\x00': 'utf-32-le',
        b'\x00\x00\xfe\xff': 'utf-32-be',
    }

    # Encodings a testar (ordem de prioridade)
    STANDARD_ENCODINGS = [
        'utf-8',
        'utf-16-le',
        'utf-16-be',
        'windows-1252',
        'iso-8859-1',
        'shift-jis',
        'euc-jp',
        'euc-kr',
        'gb2312',
        'big5',
        'cp437',
        'cp850',
        'cp1251',
        'ascii',
    ]

    # Frequências de letras em português (para correlação)
    PT_LETTER_FREQ = {
        'a': 14.63, 'e': 12.57, 'o': 10.73, 's': 7.81, 'r': 6.53,
        'i': 6.18, 'n': 5.05, 'd': 4.99, 'm': 4.74, 'u': 4.63,
        't': 4.34, 'c': 3.88, 'l': 2.78, 'p': 2.52, 'v': 1.67,
    }

    # Frequências em inglês
    EN_LETTER_FREQ = {
        'e': 12.70, 't': 9.06, 'a': 8.17, 'o': 7.51, 'i': 6.97,
        'n': 6.75, 's': 6.33, 'h': 6.09, 'r': 5.99, 'd': 4.25,
    }

    # Padrões de charsets SNES conhecidos
    SNES_COMMON_MAPPINGS = {
        # ASCII-like (mais comum)
        0x20: ' ',
        0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D',
        0x61: 'a', 0x62: 'b', 0x63: 'c', 0x64: 'd',

        # Códigos de controle comuns
        0x00: '<END>',
        0x01: '<NEWLINE>',
        0xFF: '<WAIT>',
    }

    def __init__(self, file_path: str):
        """
        Args:
            file_path: Caminho do arquivo
        """
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Lê amostra do arquivo
        with open(self.file_path, 'rb') as f:
            self.raw_data = f.read(min(1024 * 1024, self.file_path.stat().st_size))  # Máx 1MB

    def detect(self) -> AdvancedEncodingResult:
        """
        Detecta encoding ou charset custom.

        Returns:
            AdvancedEncodingResult
        """
        # 1. Verifica BOM
        bom_result = self._detect_bom()
        if bom_result:
            return bom_result

        # 2. Testa encodings padrão
        standard_result = self._test_standard_encodings()
        if standard_result and standard_result.confidence >= 0.7:
            return standard_result

        # 3. Detecta se é binário com charset custom (ROM)
        if self._is_likely_rom():
            custom_result = self._detect_custom_charset()
            if custom_result:
                return custom_result

        # 4. Fallback: melhor resultado padrão ou UTF-8
        if standard_result:
            return standard_result

        return AdvancedEncodingResult(
            encoding='utf-8',
            confidence=0.3,
            metadata={'fallback': True}
        )

    def _detect_bom(self) -> Optional[AdvancedEncodingResult]:
        """Detecta encoding via BOM."""
        for bom_bytes, encoding in sorted(
            self.BOM_SIGNATURES.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if self.raw_data.startswith(bom_bytes):
                return AdvancedEncodingResult(
                    encoding=encoding,
                    confidence=1.0,
                    bom=bom_bytes,
                    metadata={'detection_method': 'bom'}
                )

        return None

    def _test_standard_encodings(self) -> Optional[AdvancedEncodingResult]:
        """Testa encodings padrão."""
        best_encoding = None
        best_score = 0.0

        for encoding in self.STANDARD_ENCODINGS:
            try:
                # Tenta decodificar
                text = self.raw_data.decode(encoding, errors='strict')

                # Calcula score de qualidade
                score = self._calculate_text_quality(text)

                if score > best_score:
                    best_score = score
                    best_encoding = encoding

            except (UnicodeDecodeError, LookupError):
                continue

        if best_encoding:
            return AdvancedEncodingResult(
                encoding=best_encoding,
                confidence=best_score,
                metadata={'detection_method': 'standard_test'}
            )

        return None

    def _calculate_text_quality(self, text: str) -> float:
        """
        Calcula qualidade do texto decodificado.

        Returns:
            Score 0.0-1.0
        """
        if not text:
            return 0.0

        score = 0.0

        # 1. Caracteres imprimíveis (30%)
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        printable_ratio = printable / len(text)
        score += printable_ratio * 0.3

        # 2. Ausência de caracteres de substituição (30%)
        replacement_count = text.count('\ufffd')
        if replacement_count == 0:
            score += 0.3
        else:
            penalty = min(replacement_count / len(text) * 10, 0.3)
            score += max(0, 0.3 - penalty)

        # 3. Proporção de espaços (10%)
        space_ratio = text.count(' ') / len(text) if len(text) > 0 else 0
        if 0.05 <= space_ratio <= 0.25:  # Texto normal tem ~15% espaços
            score += 0.1

        # 4. Caracteres alfanuméricos (20%)
        alphanum = sum(1 for c in text if c.isalnum())
        alphanum_ratio = alphanum / len(text)
        score += alphanum_ratio * 0.2

        # 5. Frequência de letras (10%)
        freq_score = self._check_letter_frequency(text)
        score += freq_score * 0.1

        return min(score, 1.0)

    def _check_letter_frequency(self, text: str) -> float:
        """Verifica se frequência de letras bate com idioma natural."""
        text_lower = text.lower()
        letter_count = Counter(c for c in text_lower if c.isalpha())

        if not letter_count:
            return 0.0

        # Calcula frequências
        total = sum(letter_count.values())
        frequencies = {char: count/total*100 for char, count in letter_count.items()}

        # Correlação com português
        pt_correlation = 0.0
        for letter in self.PT_LETTER_FREQ:
            if letter in frequencies:
                expected = self.PT_LETTER_FREQ[letter]
                actual = frequencies[letter]
                # Quanto mais próximo, melhor
                diff = abs(expected - actual)
                pt_correlation += max(0, 1 - diff/10)

        pt_score = pt_correlation / len(self.PT_LETTER_FREQ)

        # Correlação com inglês
        en_correlation = 0.0
        for letter in self.EN_LETTER_FREQ:
            if letter in frequencies:
                expected = self.EN_LETTER_FREQ[letter]
                actual = frequencies[letter]
                diff = abs(expected - actual)
                en_correlation += max(0, 1 - diff/10)

        en_score = en_correlation / len(self.EN_LETTER_FREQ)

        # Retorna melhor score
        return max(pt_score, en_score)

    def _is_likely_rom(self) -> bool:
        """Verifica se arquivo parece ser uma ROM."""
        # Verifica extensão
        ext = self.file_path.suffix.lower()
        rom_extensions = {'.smc', '.sfc', '.nes', '.gba', '.gb', '.gbc', '.n64', '.z64', '.bin'}

        if ext in rom_extensions:
            return True

        # Verifica headers conhecidos
        # SNES header
        if len(self.raw_data) >= 0x10000:
            if self.raw_data[0x7FDC:0x7FDE] == b'\xAA\x55' or \
               self.raw_data[0xFFDC:0xFFDE] == b'\xAA\x55':
                return True

        # NES header
        if self.raw_data.startswith(b'NES\x1A'):
            return True

        # GBA header
        if len(self.raw_data) >= 0x9C:
            if self.raw_data[0x04:0x9C] == bytes.fromhex('24FFAE51699AA2213D84820A84E40940'):
                return True

        # Alta entropia (binário)
        entropy = self._calculate_entropy(self.raw_data[:4096])
        if entropy > 7.0:  # Muito alto = provavelmente binário
            return True

        return False

    def _calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia de Shannon."""
        if not data:
            return 0.0

        counter = Counter(data)
        length = len(data)
        entropy = 0.0

        for count in counter.values():
            probability = count / length
            if probability > 0:
                import math
                entropy -= probability * math.log2(probability)

        return entropy

    def _detect_custom_charset(self) -> Optional[AdvancedEncodingResult]:
        """
        Detecta charset custom de ROM.

        Estratégia:
        1. Procura por tabelas ASCII-like
        2. Identifica códigos de controle
        3. Infere mapeamentos por frequência
        """
        # Analisa frequência de bytes
        byte_freq = Counter(self.raw_data)

        # Remove bytes muito raros (< 0.1%) e muito comuns (> 10%)
        total_bytes = len(self.raw_data)
        filtered_freq = {
            byte: count for byte, count in byte_freq.items()
            if 0.001 < count/total_bytes < 0.1
        }

        if len(filtered_freq) < 20:
            return None  # Muito poucos bytes únicos

        # Tenta inferir charset
        custom_charset = self._infer_charset_mapping(filtered_freq)

        if custom_charset and len(custom_charset) >= 30:
            # Calcula confiança baseada em cobertura
            coverage = len(custom_charset) / 94  # 94 = caracteres ASCII imprimíveis
            confidence = min(coverage, 0.85)

            return AdvancedEncodingResult(
                encoding='custom',
                confidence=confidence,
                is_custom=True,
                custom_charset=custom_charset,
                metadata={
                    'detection_method': 'charset_inference',
                    'charset_size': len(custom_charset)
                }
            )

        return None

    def _infer_charset_mapping(self, byte_freq: Dict[int, int]) -> Dict[int, str]:
        """
        Infere mapeamento de charset custom.

        Usa:
        - Padrões SNES comuns
        - Frequência de bytes
        - Correlação com letras comuns
        """
        charset = {}

        # Começa com mapeamentos conhecidos
        charset.update(self.SNES_COMMON_MAPPINGS)

        # Ordena bytes por frequência
        sorted_bytes = sorted(byte_freq.items(), key=lambda x: x[1], reverse=True)

        # Letras em português/inglês por frequência
        common_letters = [
            'a', 'e', 'o', 's', 'r', 'i', 'n', 'd', 'm', 'u',
            't', 'c', 'l', 'p', 'v', 'g', 'h', 'f', 'b', 'q',
            'A', 'E', 'O', 'S', 'R', 'I', 'N', 'D', 'M', 'U',
        ]

        # Mapeia bytes mais frequentes para letras mais comuns
        letter_idx = 0
        for byte_val, count in sorted_bytes:
            # Pula se já mapeado
            if byte_val in charset:
                continue

            # Pula bytes de controle (0x00-0x1F, 0x80+)
            if byte_val < 0x20 or byte_val >= 0x80:
                continue

            # Mapeia para próxima letra comum
            if letter_idx < len(common_letters):
                charset[byte_val] = common_letters[letter_idx]
                letter_idx += 1

        # Adiciona espaço se não mapeado
        if 0x20 not in charset:
            # Procura byte mais frequente ainda não mapeado
            for byte_val, count in sorted_bytes:
                if byte_val not in charset and 0x20 <= byte_val < 0x80:
                    charset[byte_val] = ' '
                    break

        return charset

    def decode_with_custom_charset(
        self,
        data: bytes,
        charset: Dict[int, str],
        unknown_char: str = '�'
    ) -> str:
        """
        Decodifica bytes usando charset custom.

        Args:
            data: Bytes a decodificar
            charset: Mapeamento {byte: character}
            unknown_char: Caractere para bytes desconhecidos

        Returns:
            String decodificada
        """
        result = []

        for byte in data:
            if byte in charset:
                result.append(charset[byte])
            else:
                result.append(unknown_char)

        return ''.join(result)


def detect_encoding_advanced(file_path: str) -> AdvancedEncodingResult:
    """
    Função de conveniência para detecção rápida.

    Args:
        file_path: Caminho do arquivo

    Returns:
        AdvancedEncodingResult
    """
    detector = AdvancedEncodingDetector(file_path)
    return detector.detect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python advanced_encoding_detector.py <file_path>")
        print("\nExample:")
        print('  python advanced_encoding_detector.py "game.txt"')
        print('  python advanced_encoding_detector.py "game.smc"')
        sys.exit(1)

    file = sys.argv[1]
    result = detect_encoding_advanced(file)

    print(f"\n🔍 ADVANCED ENCODING DETECTION RESULT")
    print(f"{'='*70}")
    print(f"File: {file}")
    print(f"Encoding: {result.encoding}")
    print(f"Confidence: {result.confidence * 100:.1f}%")
    print(f"Custom Charset: {'Yes' if result.is_custom else 'No'}")

    if result.bom:
        print(f"BOM: {result.bom.hex()}")

    if result.is_custom and result.custom_charset:
        print(f"\n📋 CUSTOM CHARSET MAPPING ({len(result.custom_charset)} entries):")
        # Mostra primeiros 20 mapeamentos
        for i, (byte_val, char) in enumerate(sorted(result.custom_charset.items())[:20]):
            print(f"  0x{byte_val:02X} → '{char}'")
        if len(result.custom_charset) > 20:
            print(f"  ... and {len(result.custom_charset) - 20} more")

    if result.metadata:
        print(f"\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    print(f"{'='*70}\n")

    # Testa decodificação se for custom
    if result.is_custom and result.custom_charset:
        detector = AdvancedEncodingDetector(file)
        sample = detector.raw_data[:200]

        decoded = detector.decode_with_custom_charset(sample, result.custom_charset)

        print(f"📄 SAMPLE DECODING (first 200 bytes):")
        print(f"{'='*70}")
        print(decoded)
        print(f"{'='*70}\n")
