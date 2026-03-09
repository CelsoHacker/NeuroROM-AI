# -*- coding: utf-8 -*-
import os
import sys
import math
import threading
from collections import Counter
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# Adiciona diretório core ao path
_CORE_DIR = Path(__file__).parent.parent / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

# ================================================================
# FORENSIC ERA DETECTION SYSTEM
# ================================
class ForensicEraDetector:
    ERA_LEGACY_DOS = "DOS_LEGACY"
    ERA_TRANSITION_GOLDEN = "GOLDEN_TRANSITION"
    ERA_MODERN_ENGINE = "MODERN_ENGINE"

    FORENSIC_SIGNATURES = {
        b'UnityFS': (ERA_MODERN_ENGINE, 'Unity Engine', ['utf-8', 'utf-16-le']),
        b'PE\x00\x00': (ERA_TRANSITION_GOLDEN, 'Windows PE Executable', ['ascii', 'utf-16-le']),
        b'MZ': (ERA_LEGACY_DOS, 'DOS Executable', ['ascii']),
    }

    @staticmethod
    def detect_era(file_path):
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8192)
            for signature, (era, engine, encodings) in ForensicEraDetector.FORENSIC_SIGNATURES.items():
                if signature in header:
                    rigor = 0.9 if era == ForensicEraDetector.ERA_LEGACY_DOS else 0.7
                    return (era, engine, encodings, rigor)
            return (ForensicEraDetector.ERA_TRANSITION_GOLDEN, 'Generic Binary', ['ascii', 'utf-8'], 0.7)
        except:
            return (ForensicEraDetector.ERA_TRANSITION_GOLDEN, 'Unknown', ['ascii', 'utf-8'], 0.7)

# ================================================================
# NEURAL SCORING SYSTEM (Ajustado para Retro)
# ================================
class NeuralScorer:
    @staticmethod
    def calculate_score(text, era, rigor_level):
        if not text or len(text) < 2: # Aceita "UP", "ON"
            return False

        # Bônus para palavras curtas alfanuméricas (Mario)
        if 2 <= len(text) <= 4 and text.isalnum():
            return True

        score = 0.0
        # Bônus para Maiúsculas (S-Type Systems)
        if text.isupper(): score += 0.3

        # Vogais relaxadas
        vowels = set('aeiouAEIOUáéíóúyY')
        v_count = sum(1 for c in text if c in vowels)
        if v_count > 0 or len(text) < 5: score += 0.3

        # Entropia de Shannon Básica
        counts = Counter(text)
        entropy = -sum((count/len(text)) * math.log2(count/len(text)) for count in counts.values())
        if entropy < 5.0: score += 0.2

        return score >= 0.35

# ================================================================
# EXTRACTION WORKER ELITE - FINAL VERSION (Mario Fix)
# ================================
class ExtractionWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)

    def __init__(self, rom_path, pointer_offset, num_entries, sampling_mode=False, parent=None):
        super().__init__(parent)
        self.rom_path = rom_path
        self.pointer_offset = pointer_offset
        self.num_entries = num_entries
        self.sampling_mode = sampling_mode
        self.shift_key = 0 # Chave para decifrar DKKN -> HELLO
        self.cancel_flag = threading.Event()
        self.era = None
        self.rigor_level = 0.7

    def _auto_detect_encoding_shift(self, data_sample):
        """Detecta o segredo da Nintendo (Shift). No Mario costuma ser +1."""
        keywords = [b'START', b'SELECT', b'GAME', b'OVER', b'WORLD', b'TIME']
        best_shift = 0
        max_matches = 0
        for shift in range(-20, 21):
            shifted = bytearray([(b + shift) % 256 for b in data_sample])
            matches = sum(1 for w in keywords if w in shifted or w.lower() in shifted)
            if matches > max_matches:
                max_matches = matches
                best_shift = shift
        # Se for SNES e falhar na detecção, força o padrão do Mario (+1)
        if max_matches < 2 and self.rom_path.lower().endswith(('.smc', '.sfc')):
            return 1
        return best_shift

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        try:
            self.progress.emit(1, f"Iniciando análise: {os.path.basename(self.rom_path)}")

            # ROTEAMENTO PRIORITÁRIO PARA SMS/GG/SG
            file_ext = os.path.splitext(self.rom_path)[1].lower()
            if file_ext in ['.sms', '.gg', '.sg']:
                result = self._extract_sms_pro()
                self.finished.emit(result)
                return

            # 1. Detectar Era e Shift (para outros formatos)
            self.era, _, _, self.rigor_level = ForensicEraDetector.detect_era(self.rom_path)

            with open(self.rom_path, 'rb') as f:
                sample = f.read(65536)
            self.shift_key = self._auto_detect_encoding_shift(sample)

            if self.shift_key != 0:
                self.progress.emit(10, f"Shift detectado: {self.shift_key:+d}")

            # 2. Executar extração universal com o Shift_Key
            result = self._extract_universal_elite()
            self.finished.emit(result)

        except Exception as e:
            self.progress.emit(0, f"ERRO: {str(e)}")
            self.finished.emit({'strings': [], 'total': 0, 'error': str(e)})

    def _extract_sms_pro(self):
        """Extração SMS PRO com fail-fast e quality gates."""
        try:
            from sms_pro_extractor import SMSProExtractor
        except ImportError:
            try:
                from core.sms_pro_extractor import SMSProExtractor
            except ImportError:
                self.progress.emit(0, "ERRO: SMS PRO Extractor não encontrado")
                return {'strings': [], 'total': 0, 'error': 'SMS PRO não disponível'}

        self.progress.emit(5, "SMS detectado - Usando SMS PRO Extractor")
        self.progress.emit(10, "Descobrindo tabelas de ponteiros...")

        try:
            extractor = SMSProExtractor(self.rom_path)
            self.progress.emit(20, f"CRC32: {extractor.crc32}")

            result = extractor.extract()

            if not result.success:
                self.progress.emit(100, f"FAIL-FAST: {result.error_message}")
                return {
                    'strings': [],
                    'total': 0,
                    'error': result.error_message,
                    'diagnostics': result.diagnostics,
                    'safe_ratio': result.safe_ratio
                }

            self.progress.emit(80, f"Extraídos: {result.total_extracted} | Safe: {result.safe_ratio:.0%}")

            # Converte para formato esperado pela UI
            strings = []
            for item in extractor.items:
                strings.append({
                    'id': item.id,
                    'original': item.decoded_text,
                    'translated': '',
                    'snes_addr': f'0x{item.file_offset:06X}',
                    'category': item.method.value,
                    'confidence': item.confidence,
                    'is_safe': item.is_decoded and item.confidence > 0.6
                })

            self.progress.emit(100, f"SMS PRO: {len(strings)} strings | Safe: {result.safe_ratio:.0%}")

            return {
                'strings': strings,
                'total': len(strings),
                'method': result.method.value,
                'safe_ratio': result.safe_ratio,
                'crc32': extractor.crc32
            }

        except Exception as e:
            self.progress.emit(0, f"Erro SMS PRO: {str(e)}")
            return {'strings': [], 'total': 0, 'error': str(e)}

    def _extract_ascii_from_chunk(self, chunk):
        strings = []
        current_bytes = bytearray()
        for byte in chunk:
            # APLICA A CORREÇÃO DE TABELA (Mágica para o Mario)
            decoded_byte = (byte + self.shift_key) % 256
            if 0x20 <= decoded_byte <= 0x7E:
                current_bytes.append(decoded_byte)
            else:
                if len(current_bytes) >= 2:
                    try:
                        text = current_bytes.decode('utf-8', errors='ignore').strip()
                        if text: strings.append(text)
                    except: pass
                current_bytes = bytearray()
        return strings

    def _extract_universal_elite(self):
        file_size = os.path.getsize(self.rom_path)
        all_strings = []
        CHUNK_SIZE = 1024 * 1024 # 1MB

        with open(self.rom_path, 'rb') as f:
            pos = 0
            while pos < file_size:
                if self.cancel_flag.is_set(): break
                chunk = f.read(CHUNK_SIZE)
                if not chunk: break

                batch = self._extract_ascii_from_chunk(chunk)
                all_strings.extend(batch)
                pos += CHUNK_SIZE
                self.progress.emit(20 + int((pos/file_size)*60), "Varrendo ROM...")

        unique_texts = list(set(all_strings))
        final_data = []
        for i, txt in enumerate(unique_texts):
            if NeuralScorer.calculate_score(txt, self.era, self.rigor_level):
                final_data.append({
                    'id': i, 'original': txt, 'translated': '', 'snes_addr': 'DECIPHERED'
                })

        self.progress.emit(100, f"✅ Sucesso! {len(final_data)} strings prontas.")
        return {'strings': final_data, 'total': len(final_data)}