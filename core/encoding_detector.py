# -*- coding: utf-8 -*-
"""
================================================================================
ENCODING DETECTOR - Detecção e Preservação de Encoding de Arquivos
================================================================================
Detecta automaticamente o encoding correto de arquivos de texto:
- UTF-8 (com e sem BOM)
- UTF-16 (LE/BE)
- UTF-32 (LE/BE)
- Windows-1252 (Western European)
- ISO-8859-1 (Latin-1)
- Shift-JIS (Japonês)
- GB2312/GBK (Chinês)
- EUC-KR (Coreano)

CRÍTICO: Preserva encoding original para reinserção sem corrupção
================================================================================
"""

import chardet
from pathlib import Path
from typing import Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class EncodingResult:
    """Resultado da detecção de encoding."""
    encoding: str
    confidence: float
    bom: Optional[bytes]
    validated: bool
    fallback_used: bool
    error_message: Optional[str] = None

    def __repr__(self):
        status = "✓" if self.validated else "✗"
        return (f"<EncodingResult {status} {self.encoding} "
                f"confidence={self.confidence:.2f} bom={self.bom is not None}>")


class EncodingDetector:
    """
    Detector robusto de encoding com validação.

    Estratégia multi-camada:
    1. Detecta BOM (Byte Order Mark) - 100% confiável
    2. Usa chardet library - 70-95% confiável
    3. Tenta decodificar com encodings comuns
    4. Validação: re-encode e compara
    """

    # BOM signatures (Byte Order Marks)
    BOM_SIGNATURES = {
        b'\xef\xbb\xbf': 'utf-8-sig',
        b'\xff\xfe\x00\x00': 'utf-32-le',
        b'\x00\x00\xfe\xff': 'utf-32-be',
        b'\xff\xfe': 'utf-16-le',
        b'\xfe\xff': 'utf-16-be',
    }

    # Encodings para testar em ordem de prioridade
    COMMON_ENCODINGS = [
        'utf-8',
        'utf-16-le',
        'utf-16-be',
        'windows-1252',  # Western European (Windows)
        'iso-8859-1',    # Latin-1
        'cp1251',        # Cyrillic
        'shift-jis',     # Japanese
        'gb2312',        # Simplified Chinese
        'gbk',           # Extended Chinese
        'euc-kr',        # Korean
        'iso-8859-2',    # Central European
        'iso-8859-15',   # Latin-9
    ]

    def __init__(self, file_path: str):
        """
        Args:
            file_path: Caminho do arquivo para detectar encoding
        """
        self.file_path = Path(file_path)
        self.raw_data: Optional[bytes] = None
        self.result: Optional[EncodingResult] = None

    def detect(self, sample_size: int = 32768) -> EncodingResult:
        """
        Detecta encoding do arquivo.

        Args:
            sample_size: Bytes para ler (default: 32KB, suficiente para detecção)

        Returns:
            EncodingResult com encoding detectado e validado
        """
        if not self.file_path.exists():
            return EncodingResult(
                encoding='utf-8',
                confidence=0.0,
                bom=None,
                validated=False,
                fallback_used=True,
                error_message=f"File not found: {self.file_path}"
            )

        # Lê amostra do arquivo
        try:
            with open(self.file_path, 'rb') as f:
                self.raw_data = f.read(sample_size)
        except Exception as e:
            return EncodingResult(
                encoding='utf-8',
                confidence=0.0,
                bom=None,
                validated=False,
                fallback_used=True,
                error_message=f"Error reading file: {e}"
            )

        if not self.raw_data:
            return EncodingResult(
                encoding='utf-8',
                confidence=1.0,
                bom=None,
                validated=True,
                fallback_used=False
            )

        # Etapa 1: Verifica BOM (100% confiável)
        bom_result = self._detect_bom()
        if bom_result:
            self.result = bom_result
            return self.result

        # Etapa 2: Usa chardet (biblioteca de detecção)
        chardet_result = self._detect_with_chardet()
        if chardet_result and chardet_result.confidence >= 0.8:
            # Alta confiança do chardet
            validated = self._validate_encoding(chardet_result.encoding)
            if validated:
                self.result = chardet_result
                return self.result

        # Etapa 3: Testa encodings comuns
        manual_result = self._detect_manually()
        if manual_result:
            self.result = manual_result
            return self.result

        # Etapa 4: Fallback para UTF-8 ou Windows-1252
        fallback_result = self._fallback_encoding()
        self.result = fallback_result
        return self.result

    def _detect_bom(self) -> Optional[EncodingResult]:
        """Detecta encoding via BOM (Byte Order Mark)."""
        # Verifica assinaturas de BOM em ordem de tamanho (maior primeiro)
        for bom_bytes, encoding in sorted(
            self.BOM_SIGNATURES.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if self.raw_data.startswith(bom_bytes):
                # Valida decodificação
                try:
                    # Remove BOM e tenta decodificar
                    test_data = self.raw_data[len(bom_bytes):]
                    test_data.decode(encoding)

                    return EncodingResult(
                        encoding=encoding,
                        confidence=1.0,
                        bom=bom_bytes,
                        validated=True,
                        fallback_used=False
                    )
                except UnicodeDecodeError:
                    # BOM presente mas encoding não funciona (arquivo corrompido?)
                    pass

        return None

    def _detect_with_chardet(self) -> Optional[EncodingResult]:
        """Detecta usando biblioteca chardet."""
        try:
            detection = chardet.detect(self.raw_data)

            if not detection or not detection.get('encoding'):
                return None

            encoding = detection['encoding'].lower()
            confidence = detection.get('confidence', 0.0)

            # Normaliza nomes de encoding
            encoding = self._normalize_encoding_name(encoding)

            return EncodingResult(
                encoding=encoding,
                confidence=confidence,
                bom=None,
                validated=False,  # Será validado depois
                fallback_used=False
            )

        except Exception as e:
            print(f"⚠️  chardet detection failed: {e}")
            return None

    def _normalize_encoding_name(self, encoding: str) -> str:
        """Normaliza nomes de encoding para consistência."""
        encoding = encoding.lower().replace('-', '').replace('_', '')

        # Mapeamento de aliases comuns
        aliases = {
            'utf8': 'utf-8',
            'utf16': 'utf-16',
            'ascii': 'utf-8',  # ASCII é subconjunto de UTF-8
            'latin1': 'iso-8859-1',
            'windows1252': 'windows-1252',
            'cp1252': 'windows-1252',
            'shiftjis': 'shift-jis',
            'eucjp': 'euc-jp',
            'euckr': 'euc-kr',
            'gb2312': 'gbk',  # GBK é superset de GB2312
        }

        for alias, canonical in aliases.items():
            if encoding.startswith(alias):
                return canonical

        # Restaura formato correto
        if encoding.startswith('utf'):
            return encoding[:3] + '-' + encoding[3:]
        if encoding.startswith('iso'):
            return 'iso-8859-' + encoding.replace('iso', '').replace('8859', '')

        return encoding

    def _validate_encoding(self, encoding: str) -> bool:
        """
        Valida encoding tentando decodificar e re-encodar.

        Returns:
            True se encoding é válido (round-trip funciona)
        """
        try:
            # Decodifica
            text = self.raw_data.decode(encoding, errors='strict')

            # Re-encode
            re_encoded = text.encode(encoding)

            # Compara (deve ser idêntico)
            # Nota: Alguns encodings podem ter variações (ex: line endings)
            # então verificamos apenas que não houve perda significativa
            similarity = len(re_encoded) / len(self.raw_data) if self.raw_data else 0

            return 0.95 <= similarity <= 1.05

        except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
            return False

    def _detect_manually(self) -> Optional[EncodingResult]:
        """Tenta manualmente encodings comuns."""
        best_encoding = None
        best_score = 0.0

        for encoding in self.COMMON_ENCODINGS:
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

        if best_encoding and best_score > 0.7:
            return EncodingResult(
                encoding=best_encoding,
                confidence=best_score,
                bom=None,
                validated=True,
                fallback_used=False
            )

        return None

    def _calculate_text_quality(self, text: str) -> float:
        """
        Calcula score de qualidade do texto decodificado.

        Heurísticas:
        - Proporção de caracteres imprimíveis
        - Ausência de caracteres de controle estranhos
        - Presença de palavras reconhecíveis
        """
        if not text:
            return 0.0

        score = 0.0

        # 1. Caracteres imprimíveis (40%)
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        printable_ratio = printable / len(text)
        score += printable_ratio * 0.4

        # 2. Ausência de caracteres de substituição (30%)
        replacement_chars = text.count('\ufffd')  # Unicode replacement character
        if replacement_chars == 0:
            score += 0.3
        else:
            penalty = min(replacement_chars / len(text) * 10, 0.3)
            score += max(0, 0.3 - penalty)

        # 3. Proporção de espaços (10%)
        spaces = text.count(' ')
        space_ratio = spaces / len(text)
        # Texto normal tem ~15% de espaços
        if 0.05 <= space_ratio <= 0.25:
            score += 0.1

        # 4. Caracteres alfanuméricos (20%)
        alphanum = sum(1 for c in text if c.isalnum())
        alphanum_ratio = alphanum / len(text)
        score += alphanum_ratio * 0.2

        return min(score, 1.0)

    def _fallback_encoding(self) -> EncodingResult:
        """Encoding de fallback quando detecção falha."""
        # Tenta UTF-8 primeiro
        try:
            self.raw_data.decode('utf-8', errors='strict')
            return EncodingResult(
                encoding='utf-8',
                confidence=0.5,
                bom=None,
                validated=True,
                fallback_used=True
            )
        except UnicodeDecodeError:
            pass

        # Fallback final: windows-1252 (quase sempre funciona)
        # Mas marca como baixa confiança
        return EncodingResult(
            encoding='windows-1252',
            confidence=0.3,
            bom=None,
            validated=False,
            fallback_used=True,
            error_message="Using fallback encoding (detection failed)"
        )

    def read_file(self, encoding: Optional[str] = None) -> Tuple[Optional[str], str]:
        """
        Lê arquivo completo com encoding detectado.

        Args:
            encoding: Encoding específico (ou None para usar detectado)

        Returns:
            (conteúdo_texto, encoding_usado)
        """
        if encoding is None:
            if self.result is None:
                self.detect()
            encoding = self.result.encoding

        try:
            with open(self.file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
            return content, encoding
        except Exception as e:
            print(f"❌ Error reading file with {encoding}: {e}")
            return None, encoding

    def get_encoding_info(self) -> Dict:
        """
        Retorna informações completas sobre encoding detectado.

        Returns:
            Dicionário com metadados de encoding
        """
        if self.result is None:
            self.detect()

        return {
            'file_path': str(self.file_path),
            'encoding': self.result.encoding,
            'confidence': round(self.result.confidence, 3),
            'has_bom': self.result.bom is not None,
            'bom_bytes': self.result.bom.hex() if self.result.bom else None,
            'validated': self.result.validated,
            'fallback_used': self.result.fallback_used,
            'error': self.result.error_message,
            'file_size': self.file_path.stat().st_size if self.file_path.exists() else 0
        }


def detect_file_encoding(file_path: str) -> EncodingResult:
    """
    Função de conveniência para detecção rápida.

    Args:
        file_path: Caminho do arquivo

    Returns:
        EncodingResult com encoding detectado
    """
    detector = EncodingDetector(file_path)
    return detector.detect()


def batch_detect_encodings(file_paths: list) -> Dict[str, EncodingResult]:
    """
    Detecta encoding de múltiplos arquivos.

    Args:
        file_paths: Lista de caminhos de arquivos

    Returns:
        Dicionário {filepath: EncodingResult}
    """
    results = {}

    print(f"\n📝 BATCH ENCODING DETECTION")
    print(f"{'='*70}")
    print(f"Detecting encodings for {len(file_paths)} files...\n")

    for i, file_path in enumerate(file_paths, 1):
        result = detect_file_encoding(file_path)
        results[file_path] = result

        status = "✓" if result.validated else "⚠"
        print(f"  {i:3d}. {status} {Path(file_path).name:40s} → {result.encoding:15s} "
              f"(conf: {result.confidence:.2f})")

    print(f"\n{'='*70}\n")

    return results


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python encoding_detector.py <file_path> [--json]")
        print("\nExamples:")
        print("  python encoding_detector.py data/strings.txt")
        print("  python encoding_detector.py data/strings.txt --json")
        sys.exit(1)

    file = sys.argv[1]
    output_json = '--json' in sys.argv

    detector = EncodingDetector(file)
    result = detector.detect()

    if output_json:
        # Saída JSON
        info = detector.get_encoding_info()
        print(json.dumps(info, indent=2))
    else:
        # Saída legível
        print(f"\n📄 ENCODING DETECTION RESULT")
        print(f"{'='*70}")
        print(f"File: {file}")
        print(f"Encoding: {result.encoding}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Has BOM: {'Yes' if result.bom else 'No'}")
        if result.bom:
            print(f"BOM bytes: {result.bom.hex()}")
        print(f"Validated: {'✓ Yes' if result.validated else '✗ No'}")
        print(f"Fallback used: {'Yes' if result.fallback_used else 'No'}")
        if result.error_message:
            print(f"Error: {result.error_message}")

        # Tenta ler e mostrar preview
        print(f"\n{'='*70}")
        print("TEXT PREVIEW (first 500 chars):")
        print(f"{'='*70}")

        content, _ = detector.read_file()
        if content:
            preview = content[:500]
            print(preview)
            if len(content) > 500:
                print(f"\n... ({len(content) - 500} more characters)")
        else:
            print("❌ Could not read file")

        print(f"\n{'='*70}\n")
