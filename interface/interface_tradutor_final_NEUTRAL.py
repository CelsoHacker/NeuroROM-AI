"""
================================================================================
ROM Translation Framework - Main Interface
================================================================================
Universal ROM Translation Framework
Platforms: NES, SMS, MD, SNES (V1)
================================================================================
"""

import sys
import os
import zlib
import json
import subprocess
import re
import shutil
import traceback
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# ================== CONFIGURAÇÃO DO SYS.PATH ==================
# Adicione o diretório raiz do projeto para que os módulos core sejam encontrados
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def _sanitize_error(msg) -> str:
    """Remove possíveis API keys / tokens de mensagens de erro."""
    s = str(msg)
    s = re.sub(r'AIza[0-9A-Za-z\-_]{10,}', '[REDACTED]', s)
    s = re.sub(r'([?&]key=)[^&\s]+', r'\1[REDACTED]', s)
    s = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{10,}', r'\1[REDACTED]', s)
    s = re.sub(r'sk-[A-Za-z0-9]{10,}', 'sk-[REDACTED]', s)
    return s


from PyQt6.QtCore import Qt
# Banco de dados removido - sistema agora usa AUTO-DISCOVERY
# from core.MASTER_SYSTEM_COMPLETE_DATABASE_FIXED import CompleteMasterSystemExtractor

# Agora você pode importar módulos de core
try:
    from core import gemini_translator
    print("[OK]gemini_translator module importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar gemini_translator: {_sanitize_error(e)}")
    gemini_translator = None

try:
    from core.qa_gate_runtime import (
        run_qa_gate,
        run_autoretry_for_translation,
    )
except Exception:
    run_qa_gate = None
    run_autoretry_for_translation = None

try:
    from core.engine_detector import EngineDetector, detect_game_engine
    print("[OK]EngineDetector importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar EngineDetector: {_sanitize_error(e)}")
    # Fallback para desenvolvimento
    def detect_game_engine(file_path):
        return {
            'type': 'UNKNOWN',
            'platform': 'Unknown',
            'engine': 'Unknown',
            'notes': 'Engine detector não disponível'
        }

# RTCE (Runtime Text Capture Engine)
try:
    from rtce_core import RTCEEngine, TextCaptureOrchestrator
    print("[OK]RTCE module importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar RTCE: {_sanitize_error(e)}")
    RTCEEngine = None
    TextCaptureOrchestrator = None

# Continue com os outros imports...
from collections import defaultdict

# Optional dependencies with graceful fallbacks
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False
    print("Warning: numpy not available. Some features may be limited.")

try:
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    RandomForestClassifier = None
    joblib = None
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available. ML features disabled.")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False
    print("Warning: opencv not available. Image processing features limited.")

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    # Configure o caminho do Tesseract para Windows
    if sys.platform == 'win32':
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
except ImportError:
    pytesseract = None
    Image = None
    TESSERACT_AVAILABLE = False
    print("Warning: pytesseract/PIL not available. OCR features disabled.")

# Importações PyQt6 CORRETAS
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QComboBox,
    QProgressBar, QGroupBox, QGridLayout, QTabWidget,
    QMessageBox, QLineEdit, QSpinBox, QCheckBox, QFormLayout, QDialog,
    QScrollArea, QFrame, QGraphicsView, QGraphicsScene, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QTimer, QObject, QSize
from PyQt6.QtGui import (
    QFont, QTextCursor, QPalette, QColor, QPixmap,
    QImage, QPainter, QIcon, QBrush, QPen, QTransform
)

# Import Gemini API Module (CRITICAL - usado por GeminiWorker)
try:
    from interface import gemini_api
    print("[OK]gemini_api module importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar gemini_api: {_sanitize_error(e)}")
    gemini_api = None

# Import Security Manager
try:
    from core.security_manager import SecurityManager
    print("[OK]SecurityManager importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar SecurityManager: {_sanitize_error(e)}")
    SecurityManager = None

# Import Universal Master System Extractor (para jogos Master System)
try:
    # O arquivo MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL.py deve estar dentro da pasta core
    from core.MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL import UniversalMasterSystemExtractor
    print("[OK]UniversalMasterSystemExtractor importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar UniversalMasterSystemExtractor: {_sanitize_error(e)}")
    UniversalMasterSystemExtractor = None

# Import GUI Tabs
try:
    from interface.gui_tabs.graphic_lab import GraphicLabTab
    print("[OK]GraphicLabTab importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar GraphicLabTab: {_sanitize_error(e)}")
    GraphicLabTab = None

# Import Forensic Engine Upgrade (Tier 1 Detection System)
try:
    from interface.forensic_engine_upgrade import (
        EngineDetectionWorkerTier1,
        FORENSIC_SIGNATURES_TIER1,
        calculate_entropy_shannon,
        estimate_year_from_binary,
        calculate_confidence_score,
        analyze_compression_type
    )
    print("[OK]Forensic Engine Tier 1 importado com sucesso")
    USE_TIER1_DETECTION = True
except ImportError as e1:
    try:
        # Fallback: import direto (se executado da pasta interface)
        import sys
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        from forensic_engine_upgrade import (
            EngineDetectionWorkerTier1,
            FORENSIC_SIGNATURES_TIER1,
            calculate_entropy_shannon,
            estimate_year_from_binary,
            calculate_confidence_score,
            analyze_compression_type
        )
        print("[OK]Forensic Engine Tier 1 importado com sucesso (fallback)")
        USE_TIER1_DETECTION = True
    except ImportError as e2:
        print(f"[ERROR]Erro ao importar Forensic Engine Tier 1: {_sanitize_error(e1)} | {_sanitize_error(e2)}")
        USE_TIER1_DETECTION = False


def _crc32_file(path, chunk_size=1024 * 1024):
    """Calcula CRC32 em streaming (não carrega a ROM inteira na RAM)."""
    crc = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


# --- WORKERS (THREADS SEGURAS) ---

class ProcessThread(QThread):
    """Worker para executar scripts externos em subprocesso, seguro para a GUI."""
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, command: list):
        super().__init__()
        self.command = command
        self.process = None

    def run(self):
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=creation_flags
            )

            percent_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%')

            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.progress.emit(line)
                    match = percent_pattern.search(line)
                    if match:
                        try:
                            self.progress_percent.emit(int(float(match.group(1))))
                        except:
                            pass

            self.process.wait()

            success = self.process.returncode == 0
            if success:
                self.finished.emit(True, "Operation completed successfully")
            else:
                stderr = self.process.stderr.read().strip()
                self.finished.emit(False, f"Error code {self.process.returncode}: {stderr}")
        except Exception as e:
            self.finished.emit(False, f"Exception: {_sanitize_error(e)}")

    def terminate(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
        super().terminate()


class OptimizationWorker(QThread):
    """Worker dedicado para otimização de dados em thread separada - V 9.5 ENGINE."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)  # Retorna caminho do arquivo otimizado
    error_signal = pyqtSignal(str)

    def __init__(self, input_file: str, is_pc_game: bool = False, config: dict = None):
        super().__init__()
        self.input_file = input_file
        self.is_pc_game = is_pc_game
        self._is_running = True

        # [OK] CONFIGURAÇÕES DO OTIMIZADOR V 9.5 (Expert Mode)
        if config is None:
            config = {
                'preserve_commands': True,
                'replace_symbol': '@',
                'replace_with': ' ',
                'remove_overlaps': True
            }
        self.config = config

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.status_signal.emit("Analisando arquivo...")
            self.progress_signal.emit(10)

            with open(self.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            total_original = len(lines)
            self.log_signal.emit(f"[STATS] Linhas originais: {total_original:,}")
            self.progress_signal.emit(20)

            # FASE 1: LIMPEZA COM PARSING DO FORMATO [0xENDERECO] TextoReal
            self.status_signal.emit("Parsing formato [0xENDERECO]...")
            cleaned_texts = []
            seen_texts = set()  # Para remover duplicatas

            stats = {
                'comments': 0,
                'no_bracket': 0,
                'too_short': 0,
                'no_vowels': 0,
                'has_code_chars': 0,
                'binary_garbage': 0,  # NOVO: Filtro ultra-rigoroso
                'duplicates': 0,
                'kept': 0
            }
            # --- NOVO: Rastreadores para evitar repetições (Ecos) ---
            last_offset = -1
            last_text_len = 0

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.error_signal.emit("Operação cancelada pelo usuário")
                    return

                original_line = line.strip()

                # FILTRO 1: IGNORAR COMENTÁRIOS
                if original_line.startswith('#'):
                    stats['comments'] += 1
                    continue

                # FILTRO 2: SEPARAR O LIXO - Pegar só o texto depois do ']'
                if ']' not in original_line:
                    stats['no_bracket'] += 1
                    continue

                # Divide no primeiro ']' e pega a parte depois
                parts = original_line.split(']', 1)
                if len(parts) < 2:
                    stats['no_bracket'] += 1
                    continue
                clean_text = parts[1].strip()
                # 1. PEGA O ENDEREÇO (OFFSET) PARA COMPARAR
                try:
                    offset_hex = parts[0].replace('[', '').strip()
                    current_offset = int(offset_hex, 16)
                except:
                    continue

                # 2. [OK] SUBSTITUIÇÃO CONFIGURÁVEL (V 9.5 Expert Mode)
                replace_symbol = self.config.get('replace_symbol', '@')
                replace_with = self.config.get('replace_with', ' ')
                if replace_symbol and replace_with is not None:
                    clean_text = clean_text.replace(replace_symbol, replace_with)

                # 3. [OK] FILTRO DE ECO CONFIGURÁVEL (V 9.5 Expert Mode)
                # Se o endereço atual é menor que o fim do texto anterior, é lixo repetido.
                if self.config.get('remove_overlaps', True):
                    if current_offset < (last_offset + last_text_len):
                        stats['duplicates'] += 1
                        continue # Pula Mushroom/ushroom/shroom

                # Se passou no filtro, atualiza os rastreadores para a próxima linha
                last_offset = current_offset
                last_text_len = len(clean_text)
                # FILTRO 3: TAMANHO MÍNIMO (4 caracteres)
                # if len(clean_text) < 4:
                #    stats['too_short'] += 1
                #   continue

                # FILTRO 4: VERIFICAR VOGAIS (se não tiver vogal, não é texto real)
                # if not re.search(r'[aeiouAEIOU]', clean_text):
                #    stats['no_vowels'] += 1
                #   continue

                # FILTRO 5: [OK] REJEITAR CÓDIGOS CONFIGURÁVEL (V 9.5 Expert Mode)
                preserve_commands = self.config.get('preserve_commands', True)
                if any(char in clean_text for char in ['{', '}', '\\', '/']):
                    if self.is_pc_game and not preserve_commands:
                        # Se for PC E preserve_commands=False, colchetes e barras são LIXO técnico. DELETA.
                        stats['has_code_chars'] += 1
                        continue
                    elif self.is_pc_game and preserve_commands:
                        # Se for PC MAS preserve_commands=True, MANTÉM comandos.
                        pass
                    else:
                        # Se for Console (SNES), \s ou / são comandos de texto. SEMPRE MANTÉM.
                        pass

                # ========== FILTRO 6: ULTRA-RIGOROSO V2 (DETECTA LIXO BINÁRIO) ==========
                is_garbage = False

                # 6.1: Endereços hexadecimais e padrões numéricos
                if re.search(r'(0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]{2,}|^[0-9A-F]{4,}$|[0-9]{2,}[><@#\-\+][0-9])', clean_text):
                    stats['binary_garbage'] += 1
                    is_garbage = True

                # 6.2: Padrões hexadecimais com símbolos (!dAdBdC, @ABCD, @ABCD$&H)
                if not is_garbage:
                    # Padrão 1: Símbolos seguidos de letras maiúsculas (ex: @ABCD, #3CCC)
                    if re.search(r'[!@#$%^&*`][A-Z]{2,}', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True
                    # Padrão 2: Letras com símbolos no meio (ex: ABC$&H, 2BBB)
                    elif re.search(r'[A-Z]{2,}[\$&\*\^%#][A-Z&\$\*]', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True
                    # Padrão 3: Números com letras hexadecimais (ex: 2BBB, 3CCC)
                    elif re.search(r'[0-9][A-F]{3,}', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.3: Sequências minúsculas/maiúsculas curtas (4+ letras sem espaço)
                if not is_garbage:
                    # Minúsculas consecutivas: tuvw, ktuwv
                    if re.match(r'^[a-z`]{4,}$', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True
                    # Maiúsculas curtas sem vogais: IJYZ, DCBA, HIXY
                    elif re.match(r'^[A-Z]{4,8}$', clean_text) and not re.search(r'[AEIOU]', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.4: Sequências aleatórias (gibberish) - padrões caóticos
                if not is_garbage and len(clean_text) >= 4:
                    # Padrões como: eHV(Wb, V:FGiks, JjJ)@I@
                    if re.search(r'[A-Z][a-z][A-Z]\(|[A-Z]:[A-Z]|[A-Z][a-z][A-Z]\)', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True
                    # Muitas alternâncias maiúsc/minúsc: AaBbCc, JjJI
                    elif sum(1 for i in range(len(clean_text)-1)
                            if clean_text[i].isupper() != clean_text[i+1].isupper()) > len(clean_text) * 0.6:
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.5: Caracteres especiais excessivos (>=15% ULTRA RIGOROSO)
                if not is_garbage:
                    special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\')
                    special_count = sum(1 for char in clean_text if char in special_chars)
                    if len(clean_text) > 0 and special_count / len(clean_text) >= 0.15:
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.6: Repetição excessiva (< 30% caracteres únicos - mais permissivo)
                if not is_garbage and len(clean_text) > 5:
                    unique_chars = len(set(clean_text))
                    if unique_chars < len(clean_text) * 0.3:
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.7: Sequências com números misturados (07>37O4, 61-64+6E)
                if not is_garbage and len(clean_text) >= 6:
                    # Conta transições número→letra→número
                    num_letter_transitions = sum(1 for i in range(len(clean_text)-2)
                                                if clean_text[i].isdigit()
                                                and clean_text[i+1].isalpha()
                                                and clean_text[i+2].isdigit())
                    if num_letter_transitions >= 2:
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.8: Sequências longas sem espaços e sem palavras reais (>15 chars)
                if not is_garbage and len(clean_text) > 15 and ' ' not in clean_text:
                    # Se não tem espaço E não tem palavras comuns = provável lixo
                    stats['binary_garbage'] += 1
                    is_garbage = True

                # 6.9: Ratio de vogais/consoantes muito baixo (texto sem vogais suficientes)
                if not is_garbage and len(clean_text) >= 4:
                    vowel_count = sum(1 for c in clean_text if c.lower() in 'aeiou')
                    consonant_count = sum(1 for c in clean_text if c.isalpha() and c.lower() not in 'aeiou')
                    # RIGOROSO: ratio < 0.40 para strings curtas (4-8 chars)
                    if consonant_count > 0 and vowel_count > 0:
                        vowel_ratio = vowel_count / consonant_count
                        # Strings curtas precisam de mais vogais
                        if len(clean_text) <= 8 and vowel_ratio < 0.40:
                            stats['binary_garbage'] += 1
                            is_garbage = True
                        # Strings longas podem ter ratio menor
                        elif len(clean_text) > 8 and vowel_ratio < 0.25:
                            stats['binary_garbage'] += 1
                            is_garbage = True

                # 6.10: Caracteres repetidos consecutivos (JJJJ, AAAA, 8888, etc.)
                if not is_garbage:
                    # 4+ caracteres iguais consecutivos = lixo
                    if re.search(r'(.)\1{3,}', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.11: Começar com símbolos especiais, números ou caracteres suspeitos
                if not is_garbage:
                    # Linhas que começam com @#$%^&*`0-9 geralmente são lixo
                    if re.match(r'^[@#$%^&*`0-9\[\]\(\)]', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.12: Strings curtas/médias (4-15 chars) com caracteres especiais OU números
                if not is_garbage and 4 <= len(clean_text) <= 15:
                    # Se tiver caracteres especiais OU números em string curta/média, provável lixo
                    special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789')
                    if any(c in special_chars for c in clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.13: Padrões de tiles/gráficos (mix de maiúsc/minúsc sem sentido)
                if not is_garbage and len(clean_text) >= 5:
                    # Detecta padrões como: "iPCP", "bcBA", "den]", "nmh]O="
                    lower_count = sum(1 for c in clean_text if c.islower())
                    upper_count = sum(1 for c in clean_text if c.isupper())
                    # Se tiver mix balanceado de maiúsc/minúsc E tiver símbolos = lixo
                    if lower_count > 0 and upper_count > 0:
                        if abs(lower_count - upper_count) <= 2:  # Balanceado
                            special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789')
                            if any(c in special_chars for c in clean_text):
                                stats['binary_garbage'] += 1
                                is_garbage = True

                # 6.14: Sequências com números no meio (XO5678OX, uu5678uu5678)
                if not is_garbage and len(clean_text) >= 6:
                    # Se tiver 3+ dígitos consecutivos no meio de letras = lixo
                    if re.search(r'[A-Za-z]+[0-9]{3,}[A-Za-z]+', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.15: Repetições de padrões de 2-3 caracteres (IJIJIJ, quququ)
                if not is_garbage and len(clean_text) >= 6:
                    # Detecta padrões como: XYXYXY, quququ
                    for pattern_len in [2, 3]:
                        for i in range(len(clean_text) - pattern_len * 2):
                            pattern = clean_text[i:i+pattern_len]
                            # Verifica se o padrão se repete imediatamente
                            next_part = clean_text[i+pattern_len:i+pattern_len*2]
                            if pattern == next_part and pattern.isalpha():
                                stats['binary_garbage'] += 1
                                is_garbage = True
                                break
                        if is_garbage:
                            break

                # 6.16: Strings curtas (<8 chars) com mix maiúsc/minúsc SEM espaços
                if not is_garbage and 4 <= len(clean_text) < 8 and ' ' not in clean_text:
                    lower_count = sum(1 for c in clean_text if c.islower())
                    upper_count = sum(1 for c in clean_text if c.isupper())
                    # Se tiver ambos (mix) = provável lixo (iPCP, bcBA, JLjlEE)
                    if lower_count >= 1 and upper_count >= 1:
                        # Exceção: se for tudo letra (sem números/símbolos) e tiver padrão de palavra
                        if not clean_text.isalpha():
                            stats['binary_garbage'] += 1
                            is_garbage = True

                # 6.17: Strings que terminam com símbolos estranhos
                if not is_garbage:
                    # Termina com símbolos como: ", ], ), etc. (exceto . ! ?)
                    if re.search(r'["\]\)\|`]$', clean_text):
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.18: Strings curtas (4-8 chars) APENAS com letras mas mix caótico maiúsc/minúsc
                if not is_garbage and 4 <= len(clean_text) <= 8 and clean_text.isalpha():
                    lower_count = sum(1 for c in clean_text if c.islower())
                    upper_count = sum(1 for c in clean_text if c.isupper())
                    # Se tiver MIX de maiúsc/minúsc (ambos >= 1) E não for palavra comum = lixo
                    if lower_count >= 1 and upper_count >= 1:
                        # Verifica se não é padrão de palavra comum (CamelCase, etc)
                        # Padrão comum: Maiúsc no início + minúsc depois (Mario, Luigi, HP, etc)
                        is_common_pattern = (clean_text[0].isupper() and clean_text[1:].islower())
                        if not is_common_pattern:
                            stats['binary_garbage'] += 1
                            is_garbage = True

                # 6.19: Strings MAIÚSCULAS (4-12 chars) com letras repetidas consecutivas (padrão de lixo)
                if not is_garbage and 4 <= len(clean_text) <= 12 and clean_text.isupper():
                    # Detecta padrões: NNLVVU, IIHFHH, EKKH, AAAQQQ, VVUUVW, etc.
                    # Se tiver 2+ pares de letras duplicadas = lixo
                    duplicate_pairs = sum(1 for i in range(len(clean_text)-1)
                                         if clean_text[i] == clean_text[i+1])
                    if duplicate_pairs >= 2:
                        stats['binary_garbage'] += 1
                        is_garbage = True

                # 6.20: Strings com consoantes raras consecutivas (padrão incomum)
                if not is_garbage and 4 <= len(clean_text) <= 10:
                    # Consoantes raras: Q, X, Z, J, K, V, W (raramente aparecem juntas)
                    rare_consonants = 'QXZJKVW'
                    rare_count = sum(1 for c in clean_text.upper() if c in rare_consonants)
                    # Se tiver 3+ consoantes raras em string curta = lixo
                    if rare_count >= 3:
                        stats['binary_garbage'] += 1
                        is_garbage = True
                    # OU se começar com Qk, Xw, Zj, etc (padrões impossíveis)
                    if len(clean_text) >= 2:
                        first_two = clean_text[:2].upper()
                        impossible_starts = ['QK', 'XW', 'ZJ', 'VF', 'WH', 'XH', 'ZY', 'KX', 'JX']
                        if first_two in impossible_starts:
                            stats['binary_garbage'] += 1
                            is_garbage = True

               # EXCEÇÕES: Palavras de jogos são SEMPRE válidas
                game_words = ['mario', 'world', 'super', 'player', 'start', 'pause', 'game', 'over',
                             'score', 'time', 'level', 'stage', 'lives', 'coin', 'press', 'continue',
                             'menu', 'option', 'sound', 'music', 'jump', 'run', 'fire', 'bonus',
                             'yoshi', 'power', 'star', 'shell', 'switch', 'button', 'special', 'secret',
                             'enemy', 'boss', 'castle', 'exit', 'save', 'load', 'reset', 'friend',
                             'rescue', 'princess', 'bowser', 'luigi', 'peach', 'trapped', 'help',
                             'blocks', 'complete', 'explore', 'different', 'places', 'defeat', 'points',
                             'stomp', 'pressing', 'jumping', 'fence', 'pool', 'balance', 'further',
                             'between', 'left', 'right', 'down', 'pick', 'towards', 'spin', 'break']

                # Regra extra: Se tiver qualquer uma das palavras acima, SALVA.
                if any(word in clean_text.lower() for word in game_words):
                    is_garbage = False

                # === CORREÇÃO DE EMERGÊNCIA PARA SUPER MARIO WORLD ===
                # 1. Se for texto curto (2 ou 3 letras) e alfanumérico (UP, ON, x99), SALVA.
                if len(clean_text) >= 2 and len(clean_text) <= 3 and clean_text.replace(' ', '').isalnum():
                    is_garbage = False

                # 2. Se for tudo MAIÚSCULO (Menus do SNES), SALVA.
                if clean_text.isupper():
                    is_garbage = False
                # =====================================================

                # [OK] FILTRO DE LIXO BINÁRIO ATIVADO (20 sub-filtros rigorosos)
                # Se detectado como lixo pelos 20 filtros acima, DELETA!
                if is_garbage:
                    continue

                # FILTRO 7: DUPLICATAS
                clean_text_lower = clean_text.lower()
                if clean_text_lower in seen_texts:
                    stats['duplicates'] += 1
                    continue

                # APROVADO! Adiciona apenas o texto limpo
                seen_texts.add(clean_text_lower)
                cleaned_texts.append(clean_text)
                stats['kept'] += 1

                # Atualização de progresso
                if i % 1000 == 0:
                    progress = 20 + int((i / total_original) * 60)
                    self.progress_signal.emit(progress)

            self.progress_signal.emit(80)
            self.status_signal.emit("Salvando arquivo otimizado...")

            # Salvar arquivo otimizado (SEM os prefixos [0x...])
            output_file = self.input_file.replace("_extracted_texts.txt", "_optimized.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_optimized.txt"

            with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(cleaned_texts))

            total_removed = total_original - stats['kept']

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")
            # Relatório detalhado
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("[INFO] OTIMIZAÇÃO COM PARSING [0xENDERECO] CONCLUÍDA")
            self.log_signal.emit("=" * 60)
            self.log_signal.emit(f"[STATS] Linhas originais: {total_original:,}")
            self.log_signal.emit(f"[OK] Textos mantidos: {stats['kept']:,}")
            self.log_signal.emit(f"🗑️  Linhas removidas: {total_removed:,}")
            self.log_signal.emit("")
            self.log_signal.emit("Detalhamento das remoções:")
            self.log_signal.emit(f"  • Comentários (#): {stats['comments']:,}")
            self.log_signal.emit(f"  • Sem colchete ']': {stats['no_bracket']:,}")
            self.log_signal.emit(f"  • Muito curto (< 4 chars): {stats['too_short']:,}")
            self.log_signal.emit(f"  • Sem vogais: {stats['no_vowels']:,}")
            self.log_signal.emit(f"  • Caracteres de código ({{}}\\/) : {stats['has_code_chars']:,}")
            self.log_signal.emit(f"  [INFO] Lixo binário (hex/gibberish/tiles): {stats['binary_garbage']:,}")
            self.log_signal.emit(f"  • Duplicatas: {stats['duplicates']:,}")
            self.log_signal.emit("")
            self.log_signal.emit(f"💾 Arquivo salvo (SOMENTE TEXTOS LIMPOS): {os.path.basename(output_file)}")
            self.log_signal.emit("=" * 60)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))


# ================================================================================
# FAST EXTRACT WORKER - Extração Rápida com Super Filtro
# ================================================================================
class FastExtractWorker(QObject):
    """Worker para extração rápida com filtro inteligente."""
    progress_signal = pyqtSignal(str)
    progress_percent_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, rom_path: str):
        super().__init__()
        self.rom_path = rom_path

    def run(self):
        try:
            # Importa o módulo
            import sys
            import os
            core_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
            if core_path not in sys.path:
                sys.path.insert(0, core_path)

            from core.ultimate_extractor_v7 import UltimateExtractorV7

            # Cria extrator
            extractor = UltimateExtractorV7(self.rom_path)

            # Redireciona print para sinal
            import io
            from contextlib import redirect_stdout

            output_buffer = io.StringIO()

            self.progress_percent_signal.emit(10)
            self.progress_signal.emit("[START] Iniciando ULTIMATE EXTRACTION SUITE V7.0...")

            with redirect_stdout(output_buffer):
                results = extractor.extract_all()

            # Emite progresso
            output = output_buffer.getvalue()
            for line in output.split('\n'):
                if line.strip():
                    self.progress_signal.emit(line)

            self.progress_percent_signal.emit(100)
            self.finished_signal.emit(results)

        except Exception as e:
            self.error_signal.emit(f"Erro na extração: {_sanitize_error(e)}")


# ================================================================================
# RTCE WORKER - Runtime Text Capture Engine
# ================================================================================
class RTCEWorker(QThread):
    """O 'Cérebro' do Motor v 6.0: Captura texto da RAM em tempo real."""
    log_signal = pyqtSignal(str)
    text_found_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)

    def __init__(self, platform_name, parent=None):
        # CORREÇÃO: Isso evita o erro "unexpected type 'str'"
        super().__init__(parent)
        self.platform_name = platform_name
        self.is_running = True

    def run(self):
        try:
            from rtce_core.rtce_engine import RTCEEngine
            engine = RTCEEngine(platform=self.platform_name)
            self.log_signal.emit(f"🔍 [RTCE] Procurando emulador {self.platform_name}...")

            if engine.attach_to_process():
                self.log_signal.emit("[OK] [RTCE] Conectado! Capturando...")
                while self.is_running:
                    results = engine.scan_once()
                    for res in results:
                        self.text_found_signal.emit(f"[0x{res.offset}] {res.text}")
                    self.msleep(1000)
            else:
                self.log_signal.emit("[ERROR] [RTCE] Emulador não detectado.")
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Erro no Motor: {_sanitize_error(e)}")

    def stop(self):
        self.is_running = False

            # Callback para cada scan
    def run(self):
        try:
            import time
            from rtce_core.rtce_engine import RTCEEngine

            # Configuração do Motor
            engine = RTCEEngine(platform=self.platform_name)
            if not engine.attach_to_process():
                self.log_signal.emit("[ERROR] [RTCE] Emulador não detectado.")
                return

            self.log_signal.emit("[OK] [RTCE] Conectado! Iniciando captura...")

            # Inicializa variáveis
            self.all_texts = []
            interval = 1.0
            # Se duration não existir, usamos 300 segundos (5 min) por padrão
            duration = getattr(self, 'duration', 300)
            iterations = int(duration / interval)
            iteration = 0

            # --- LOOP PRINCIPAL DE CAPTURA ---
            while self._is_running and iteration < iterations:
                results = engine.scan_once(deduplicate=True)

                if results:
                    self.log_signal.emit(f"📝 Encontrados {len(results)} textos novos:")
                    for r in results:
                        # Log no console lateral
                        self.log_signal.emit(f"   {r.offset}: \"{r.text}\" (conf: {r.confidence:.2f})")

                        # Prepara o dado para os sinais
                        data = {
                            'texto': r.text,
                            'offset': r.offset,
                            'tipo': r.text_type,
                            'confianca': r.confidence
                        }

                        # 1. Envia para o VISOR ROXO
                        self.text_found_signal.emit(f"[0x{r.offset}] {r.text}")

                        # 2. Acumula para o arquivo final
                        self.all_texts.append(data)

                iteration += 1
                # Usamos o msleep do QThread para não travar a CPU
                self.msleep(int(interval * 1000))

            # --- FINALIZAÇÃO ---
            engine.detach_from_process()
            self.log_signal.emit(f"\n[OK] Captura concluída!")
            self.log_signal.emit(f"📁 Total de {len(self.all_texts)} textos capturados")

            # Envia a lista final para o sistema
            self.finished_signal.emit(self.all_texts)

        except Exception as e:
            self.log_signal.emit(f"[ERROR] Erro crítico no RTCE: {_sanitize_error(e)}")


class GeminiWorker(QThread):
    """
    Worker dedicado para tradução com Gemini - V 6.0 PRO SUITE
    [OK] LINGUISTIC SHIELD: Protege tags {PLAYER}, [WAIT], \\s com __PROTECTED__
    """
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)  # Retorna o caminho do arquivo final
    error_signal = pyqtSignal(str)
    realtime_signal = pyqtSignal(str, str, str)  # original, traduzido, tradutor

    def __init__(self, api_key: str, input_file: str, target_language: str = "Portuguese (Brazil)"):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self._is_running = True

        # [OK] LINGUISTIC SHIELD: Marcadores de proteção
        self.protected_tags = []  # Lista de (tag_original, placeholder)
        self.placeholder_prefix = "__PROTECTED_"

    def stop(self):
        self._is_running = False

    def protect_tags(self, text: str) -> str:
        """
        [OK] LINGUISTIC SHIELD V 6.0
        Protege tags especiais substituindo por placeholders antes da tradução

        Tags protegidas:
        - {PLAYER}, {NAME}, {ITEM}
        - [WAIT], [END], [COLOR:RED]
        - \\s, \\n, \\t

        Args:
            text: Texto original com tags

        Returns:
            Texto com placeholders
        """
        import re

        protected = text
        tag_counter = len(self.protected_tags)

        # PADRÃO 1: Tags com chaves {PLAYER}, {NAME}, etc.
        pattern_braces = r'\{[A-Z_]+\}'
        for match in re.finditer(pattern_braces, text):
            tag = match.group(0)
            placeholder = f"{self.placeholder_prefix}{tag_counter}__"
            self.protected_tags.append((tag, placeholder))
            protected = protected.replace(tag, placeholder, 1)
            tag_counter += 1

        # PADRÃO 2: Tags com colchetes [WAIT], [END], [COLOR:RED], etc.
        pattern_brackets = r'\[[\w:]+\]'
        for match in re.finditer(pattern_brackets, text):
            tag = match.group(0)
            placeholder = f"{self.placeholder_prefix}{tag_counter}__"
            self.protected_tags.append((tag, placeholder))
            protected = protected.replace(tag, placeholder, 1)
            tag_counter += 1

        # PADRÃO 3: Escape sequences \\s, \\n, \\t
        pattern_escapes = r'\\[snt]'
        for match in re.finditer(pattern_escapes, text):
            tag = match.group(0)
            placeholder = f"{self.placeholder_prefix}{tag_counter}__"
            self.protected_tags.append((tag, placeholder))
            protected = protected.replace(tag, placeholder, 1)
            tag_counter += 1

        return protected

    def restore_tags(self, text: str) -> str:
        """
        [OK] LINGUISTIC SHIELD V 6.0
        Restaura as tags originais após a tradução

        Args:
            text: Texto traduzido com placeholders

        Returns:
            Texto com tags originais restauradas
        """
        restored = text

        # Restaura na ordem inversa para evitar conflitos
        for tag, placeholder in reversed(self.protected_tags):
            restored = restored.replace(placeholder, tag)

        return restored

def run(self):
        try:
            # 1. Verifica disponibilidade da biblioteca
            if not gemini_api.GENAI_AVAILABLE:
                self.error_signal.emit(
                    "Biblioteca 'google-generativeai' não instalada.\n"
                    "Execute: pip install google-generativeai"
                )
                return

            # 2. Abre o arquivo
            with open(self.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            self.log_signal.emit(f"Iniciando tradução de {total_lines} linhas...")

            # 3. Preparação dos Lotes
            batch_size = 15
            current_batch = []
            batch_original_lines = []

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.log_signal.emit("[WARN] Tradução interrompida pelo usuário.")
                    break

                # Pula linhas nulas ou vazias preservando a estrutura do arquivo
                if line is None or not line.strip():
                    translated_lines.append("\n")
                    continue

                line_clean = line.strip()

                # [OK] LINGUISTIC SHIELD V 6.0: Protege as tags antes de enviar
                line_protected = self.protect_tags(line_clean)

                # === LÓGICA DE PROTEÇÃO PARA DICIONÁRIO MTE ===
                if "[DTE/MTE]" in line_clean:
                    # Isola o texto e mede o tamanho original para não estourar a ROM
                    partes = line_protected.split(']', 1)
                    texto_original = partes[1].strip() if len(partes) > 1 else line_protected
                    limite = len(texto_original)

                    # Formata a instrução que o Gemini vai ler dentro da lista
                    linha_para_ia = f"[{limite} chars max] {texto_original}"
                    current_batch.append(linha_para_ia)
                else:
                    # [OK] LINGUISTIC SHIELD V 6.0: Prompt otimizado para preservar tags
                    instrucao_elite = (
                        f"Você é um tradutor literário de elite. Sua prioridade é a fluidez e "
                        f"naturalidade da história para {self.target_language}, mantendo EXATAMENTE "
                        f"todas as tags __PROTECTED_N__ intactas (não traduza, não remova, não altere). "
                        f"Traduza: {line_protected}"
                    )
                    current_batch.append(instrucao_elite)

                # Guarda a linha original para backup em caso de erro da API
                batch_original_lines.append(line_clean)

                # 4. Processa o lote quando atingir o tamanho ou for a última linha
                if len(current_batch) >= batch_size or i == total_lines - 1:
                    if not current_batch:
                        continue

                    try:
                        # Chama a API
                        translations, success, error_msg = gemini_api.translate_batch(
                            current_batch,
                            self.api_key,
                            self.target_language,
                            120.0
                        )

                        if success and translations:
                            for trans in translations:
                                if trans is None or trans == "":
                                    translated_lines.append("\n")
                                else:
                                    # [OK] LINGUISTIC SHIELD V 6.0: Restaura as tags protegidas
                                    trans_restored = self.restore_tags(str(trans))
                                    # Adiciona a tradução com quebra de linha
                                    translated_lines.append(trans_restored + "\n")
                        else:
                            self.log_signal.emit(f"[WARN] Erro na API: {error_msg}")
                            # Se a API falhar, mantém o original para não perder o arquivo
                            for orig in batch_original_lines:
                                translated_lines.append(orig + "\n")

                        # Atualiza a interface
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        self.status_signal.emit(f"Traduzindo... {percent}%")

                        # Limpa os lotes para a próxima rodada
                        current_batch = []
                        batch_original_lines = []

                    except Exception as e:
                        self.log_signal.emit(f"[ERROR] Erro no processamento do lote: {_sanitize_error(e)}")
                        for orig in batch_original_lines:
                            translated_lines.append(orig + "\n")
                        current_batch = []
                        batch_original_lines = []

            # 5. Salva o arquivo final
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(translated_lines)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))

class HybridWorker(QThread):
    """Worker com fallback automático: Gemini → Ollama"""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    realtime_signal = pyqtSignal(str, str, str)  # original, traduzido, tradutor

    def __init__(self, api_key: str, input_file: str, target_language: str = "Portuguese (Brazil)"):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # Importa HybridTranslator
            try:
                from core.hybrid_translator import HybridTranslator
            except ImportError:
                self.error_signal.emit("Módulo hybrid_translator não encontrado")
                return

            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            self.log_signal.emit(f"🤖 AUTO Mode: {total_lines} linhas (Gemini primeiro, Ollama se quota esgotar)")

            # Cria tradutor híbrido
            translator = HybridTranslator(api_key=self.api_key, prefer_gemini=True)

            self.log_signal.emit(f"[OK] Gemini: {'Disponível' if translator.gemini_available else 'Indisponível'}")
            self.log_signal.emit(f"[OK] Ollama: {'Disponível' if translator.ollama_available else 'Indisponível'}")

            # Processamento em lotes - OTIMIZADO PARA VELOCIDADE MÁXIMA
            batch_size = 25  # AUMENTADO 6.6x para velocidade!
            current_batch = []

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.log_signal.emit("[WARN] Tradução interrompida pelo usuário.")
                    break

                line = line.strip()
                if not line:
                    translated_lines.append("\n")
                    continue

                current_batch.append(line)

                # Processa lote
                if len(current_batch) >= batch_size or i == total_lines - 1:
                    if not current_batch:
                        continue

                    try:
                        from core.hybrid_translator import TranslationMode

                        # Traduz com fallback automático
                        translations, success, error_msg = translator.translate_batch(
                            current_batch,
                            self.target_language,
                            TranslationMode.AUTO
                        )

                        # Mostra status atual
                        stats = translator.get_stats()

                        if success:
                            translated_lines.extend(translations)
                            # Emite sinal em tempo real (última tradução do lote)
                            if current_batch and translations:
                                last_orig = current_batch[-1] if current_batch else ""
                                last_trans = translations[-1].strip() if translations else ""
                                current_translator = "Gemini" if stats.get('gemini_requests', 0) >= stats.get('ollama_requests', 0) else "Ollama"
                                self.realtime_signal.emit(last_orig, last_trans, current_translator)
                        else:
                            self.log_signal.emit(f"[WARN] {error_msg}")
                            translated_lines.extend([l + "\n" for l in current_batch])

                        if stats['fallback_switches'] > 0 and not hasattr(self, '_fallback_warned'):
                            self.log_signal.emit(f"🔄 Mudou para Ollama (quota Gemini esgotada)")
                            self._fallback_warned = True  # Só avisa 1 vez

                        # Atualiza progresso
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        self.status_signal.emit(f"{translator.get_status_message()} - {percent}%")

                        current_batch = []

                    except Exception as e:
                        self.log_signal.emit(f"[ERROR] Erro no lote: {_sanitize_error(e)}")
                        translated_lines.extend([l + "\n" for l in current_batch])
                        current_batch = []

            # Salva arquivo
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(translated_lines)

            # Mostra estatísticas finais
            final_stats = translator.get_stats()
            self.log_signal.emit("\n" + "="*50)
            self.log_signal.emit("[STATS] ESTATÍSTICAS FINAIS:")
            self.log_signal.emit(f"   Gemini: {final_stats['gemini_requests']} requisições")
            self.log_signal.emit(f"   Ollama: {final_stats['ollama_requests']} requisições")
            self.log_signal.emit(f"   Fallbacks: {final_stats['fallback_switches']}")
            self.log_signal.emit(f"   Total traduzido: {final_stats['total_texts_translated']} textos")
            self.log_signal.emit("="*50)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))


class OllamaWorker(QThread):
    """
    Worker ULTRA-RESPONSIVO para Ollama
    FOCO: UI FLUIDA e botão Parar instantâneo
    """
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    realtime_signal = pyqtSignal(str, str, str)  # original, traduzido, tradutor

    def __init__(self, input_file: str, target_language: str = "Portuguese (Brazil)", model: str = "llama3.1:8b",
                 style: str = "classic_90s", genre: str = "auto"):
        super().__init__()
        self.input_file = input_file
        self.target_language = target_language
        self.model = model
        self.style = style  # Estilo: classic_90s, modern, literal
        self.genre = genre  # Gênero: auto, rpg, action, horror, children, sports
        self._is_running = True
        self.executor = None  # Para forçar shutdown

    def stop(self):
        """Parada INSTANTÂNEA sem esperar requests"""
        self._is_running = False
        if self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)  # Python 3.9+
            except TypeError:
                self.executor.shutdown(wait=False)  # Python 3.8 e anteriores
        self.log_signal.emit("🛑 Parada solicitada - interrompendo...")

    def _detect_optimal_workers(self):
        """
        🌡️ PROTEÇÃO TÉRMICA: Força 1 worker para evitar superaquecimento da GPU
        GTX 1060 e GPUs similares: 2+ workers = 80°C+ (crítico)
        1 worker = ~60-70°C (seguro)
        """
        return 1  # TRAVA DE SEGURANÇA: Single-thread obrigatório

    def run(self):
        try:
            import requests
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import time
            import sys
            import os

            # Importa módulos de otimização e validação ROM
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from core.translation_optimizer import TranslationOptimizer
            from core.rom_text_validator import ROMTextValidator
            from core.rom_translation_prompts import ROMTranslationPrompts

            # AUTO-START: Verifica e inicia Ollama automaticamente
            import subprocess
            ollama_running = False

            try:
                response = requests.get('http://127.0.0.1:11434/api/tags', timeout=2)
                if response.status_code == 200:
                    ollama_running = True
                    self.log_signal.emit("[OK] Ollama já está rodando")
            except:
                ollama_running = False

            # Inicia Ollama automaticamente se não estiver rodando
            if not ollama_running:
                self.log_signal.emit("[START] Iniciando Ollama automaticamente...")
                self.status_signal.emit("Iniciando Llama 3.1...")

                try:
                    # Windows: inicia sem janela visível
                    if sys.platform == 'win32':
                        CREATE_NO_WINDOW = 0x08000000
                        subprocess.Popen(
                            ['ollama', 'serve'],
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    else:
                        subprocess.Popen(
                            ['ollama', 'serve'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True
                        )

                    # Aguarda inicialização (máx 15 segundos)
                    self.log_signal.emit("⏳ Aguardando Llama 3.1 inicializar...")
                    for i in range(15):
                        time.sleep(1)
                        try:
                            response = requests.get('http://127.0.0.1:11434/api/tags', timeout=2)
                            if response.status_code == 200:
                                ollama_running = True
                                self.log_signal.emit("[OK] Llama 3.1 pronto!")
                                break
                        except:
                            self.log_signal.emit(f"⏳ Iniciando... {i+1}/15s")

                    if not ollama_running:
                        self.error_signal.emit(
                            "[ERROR] Não foi possível iniciar Llama automaticamente.\n\n"
                            "SOLUÇÃO:\n1. Abra CMD\n2. Execute: ollama serve\n3. Tente novamente"
                        )
                        return

                except FileNotFoundError:
                    self.error_signal.emit(
                        "[ERROR] Ollama não está instalado.\n\n"
                        "INSTALAÇÃO:\n1. Acesse: https://ollama.com/download\n2. Instale o Ollama\n3. Reinicie o NeuroROM AI"
                    )
                    return
                except Exception as e:
                    self.error_signal.emit(f"[ERROR] Erro ao iniciar: {_sanitize_error(e)}\n\nAbra CMD e execute: ollama serve")
                    return

            # [OK] NOVA VALIDAÇÃO: Verifica se modelo específico está instalado
            try:
                models_response = requests.get('http://127.0.0.1:11434/api/tags', timeout=5)
                if models_response.status_code == 200:
                    installed_models = models_response.json().get('models', [])
                    model_names = [m.get('name', '') for m in installed_models]

                    # Verifica se modelo existe (exato ou com variações de tag)
                    model_base = self.model.split(':')[0]  # Ex: "llama3.2" de "llama3.2:3b"
                    model_found = any(model_base in name for name in model_names)

                    if not model_found:
                        available_models = ', '.join(model_names[:5]) if model_names else 'Nenhum'
                        error_msg = (
                            f"[ERROR] ERRO: Modelo '{self.model}' NÃO está instalado.\n\n"
                            f"📋 Modelos disponíveis: {available_models}\n\n"
                            "SOLUÇÃO RÁPIDA:\n"
                            f"1. Abra um terminal/CMD\n"
                            f"2. Execute: ollama pull {self.model}\n"
                            f"3. Aguarde o download completar\n"
                            f"4. Tente traduzir novamente\n\n"
                            f"💡 ALTERNATIVA: Instale modelo menor e mais rápido:\n"
                            f"   ollama pull llama3.2:1b"
                        )
                        self.error_signal.emit(error_msg)
                        return
                    else:
                        self.log_signal.emit(f"[OK] Modelo '{self.model}' encontrado e pronto para uso")
            except Exception as e:
                self.log_signal.emit(f"[WARN] Não foi possível verificar modelos instalados: {_sanitize_error(e)}")
                # Continua mesmo assim (pode ser versão antiga do Ollama)

            # Tenta UTF-8, se falhar usa Latin-1 (aceita todos os bytes)
            try:
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines()]
            except UnicodeDecodeError:
                self.log_signal.emit("[WARN] Arquivo não é UTF-8, usando Latin-1...")
                with open(self.input_file, 'r', encoding='latin-1') as f:
                    lines = [line.strip() for line in f.readlines()]

            total_lines = len(lines)
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = str(Path(self.input_file).with_suffix('')) + "_translated.txt"

            # === FASE 1: OTIMIZAÇÃO AGRESSIVA PRÉ-TRADUÇÃO ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("🔧 FASE 1: OTIMIZAÇÃO AGRESSIVA")
            self.log_signal.emit("="*60)

            cache_file = os.path.join(os.path.dirname(self.input_file), "translation_cache.json")
            optimizer = TranslationOptimizer(cache_file=cache_file)

            self.log_signal.emit(f"[STATS] Textos originais: {total_lines:,}")
            self.log_signal.emit("🔍 Aplicando filtros: deduplicação, cache, heurísticas...")

            unique_texts, index_mapping = optimizer.optimize_text_list(
                lines,
                skip_technical=True,
                skip_proper_nouns=False,  # Mantenha False para não perder nomes de personagens
                min_entropy=0.30,
                use_cache=True
            )

            self.log_signal.emit(optimizer.get_stats_report())

            # Se não há nada para traduzir, reconstrói e salva
            if len(unique_texts) == 0:
                self.log_signal.emit("[OK] Todos os textos já em cache ou filtrados!")
                reconstructed = optimizer.reconstruct_translations([], lines, index_mapping)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(reconstructed))
                self.finished_signal.emit(output_file)
                return

            # === FASE 2: TRADUÇÃO OTIMIZADA ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("[START] FASE 2: TRADUÇÃO (SOMENTE TEXTOS ÚNICOS)")
            self.log_signal.emit("="*60)

            # DETECÇÃO AUTOMÁTICA DE WORKERS (hardware-aware)
            MAX_WORKERS = self._detect_optimal_workers()  # 1 worker = UI fluida

            # BATCH SIZE otimizado: 8-16 linhas (prompts curtos = mais estável)
            if len(unique_texts) < 1000:
                BATCH_SIZE = 12
            elif len(unique_texts) < 10000:
                BATCH_SIZE = 16
            else:
                BATCH_SIZE = 16

            self.log_signal.emit(f"⚡ Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS} (otimizado para UI fluida)")
            self.log_signal.emit("🌡️ Modo de Proteção Térmica Ativo: Adicionando intervalos para resfriamento da GPU")
            estimated_time = (len(unique_texts) / BATCH_SIZE / MAX_WORKERS) * 2.0  # Estimativa realista
            self.log_signal.emit(f"⏱️  Tempo estimado: ~{estimated_time:.1f} minutos (com respiros térmicos)")

            translated_unique = [None] * len(unique_texts)  # Pré-aloca lista

            # Inicializa validador e gerador de prompts
            validator = ROMTextValidator()
            prompt_gen = ROMTranslationPrompts()

            def is_binary_garbage(text):
                """
                FILTRO DE ENTRADA ULTRA-RIGOROSO: Detecta lixo binário/código ANTES de enviar para IA
                Retorna (is_garbage: bool, reason: str)

                VERSÃO 2.0 - MELHORIAS:
                - Detecta endereços hexadecimais (0x, $, etc.)
                - Detecta sequências aleatórias (eHV(Wb, ktuwv)
                - Detecta dados gráficos (tiles, ponteiros)
                - Valida palavras reais de jogos
                """
                import re

                if not text or not isinstance(text, str):
                    return True, "Texto vazio ou inválido"

                text_clean = text.strip()
                if len(text_clean) < 1:
                    return True, "Texto muito curto"

                # ========== EXCEÇÕES: TEXTOS VÁLIDOS DE JOGOS ==========

                # [OK] EXCEÇÃO 1: Palavras comuns de jogos (aceitar SEMPRE)
                common_game_words = {
                    # Inglês
                    'mario', 'world', 'super', 'player', 'start', 'pause', 'game', 'over',
                    'score', 'time', 'level', 'stage', 'lives', 'coin', 'press', 'continue',
                    'menu', 'option', 'sound', 'music', 'yes', 'no', 'save', 'load',
                    'exit', 'quit', 'help', 'back', 'next', 'select', 'enter', 'attack',
                    'jump', 'run', 'walk', 'fire', 'item', 'bonus', 'extra', 'power',
                    # Português
                    'jogador', 'pontos', 'vidas', 'fase', 'iniciar', 'continuar', 'sair',
                    'pausar', 'som', 'musica', 'sim', 'não', 'salvar', 'carregar', 'ajuda',
                    'voltar', 'proximo', 'selecionar', 'entrar', 'pular', 'correr', 'atirar'
                }
                text_lower = text_clean.lower()
                if any(word in text_lower for word in common_game_words):
                    return False, ""  # Válido - contém palavra de jogo

                # [OK] EXCEÇÃO 2: UI de jogo em MAIÚSCULAS (SCORE, 1UP, P1, LEVEL 1)
                game_ui_pattern = r'^[A-Z0-9\s\-]{2,15}$'
                if re.match(game_ui_pattern, text_clean) and len(text_clean.split()) <= 3:
                    # Verifica se tem pelo menos uma vogal
                    if any(c in 'AEIOU' for c in text_clean):
                        return False, ""  # Válido - é UI de jogo

                # [OK] EXCEÇÃO 3: Frases com números (Player 1, Stage 1-1, Lives: 3)
                hud_pattern = r'(player|stage|level|world|area|lives|time|score|coins?)\s*[:=\-]?\s*[\d\-]+'
                if re.search(hud_pattern, text_clean, re.IGNORECASE):
                    return False, ""  # Válido - é HUD

                # ========== FILTROS DE BLOQUEIO ==========

                # [ERROR] BLOQUEIO 1: Endereços hexadecimais e ponteiros
                hex_patterns = [
                    r'0x[0-9A-Fa-f]+',           # 0x1234, 0xABCD
                    r'\$[0-9A-Fa-f]{2,}',        # $1234, $ABCD (notação assembly)
                    r'^[0-9A-F]{4,8}$',          # 1A2B, ABCD1234 (endereços puros)
                    r'[0-9]{2,}[><\|@#][0-9]',   # 07>37, 05@T (operadores + números)
                ]
                for pattern in hex_patterns:
                    if re.search(pattern, text_clean):
                        return True, "Endereço hexadecimal/ponteiro detectado"

                # [ERROR] BLOQUEIO 2: Sequências aleatórias (gibberish)
                # Detecta textos que não têm padrão de palavras reais
                if len(text_clean) >= 4:
                    # Conta transições consoante→consoante sem vogais
                    consonants = 'bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ'
                    consonant_runs = 0
                    for i in range(len(text_clean) - 2):
                        if text_clean[i] in consonants and text_clean[i+1] in consonants and text_clean[i+2] in consonants:
                            consonant_runs += 1

                    # Se >30% do texto são runs de 3+ consoantes = gibberish
                    if consonant_runs > len(text_clean) * 0.3:
                        return True, "Sequência aleatória (gibberish) detectada"

                # [ERROR] BLOQUEIO 3: Sem vogais (lixo binário)
                vowels = set('aeiouAEIOUàáâãéêíóôõúÀÁÂÃÉÊÍÓÔÕÚ')
                if not any(char in vowels for char in text_clean):
                    return True, "Sem vogais (lixo binário)"

                # [ERROR] BLOQUEIO 4: Proporção de caracteres especiais (>50% agora)
                special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\')
                special_count = sum(1 for char in text_clean if char in special_chars)
                if len(text_clean) > 0 and special_count / len(text_clean) > 0.5:  # Reduzido para 50%
                    return True, f">50% caracteres especiais ({special_count}/{len(text_clean)})"

                # [ERROR] BLOQUEIO 5: Padrões de lixo binário específicos
                garbage_patterns = [
                    (r'^[!@#$%^&*]{3,}', "3+ símbolos consecutivos"),
                    (r'^[A-Z]{10,}$', "10+ letras maiúsculas sem espaços"),
                    (r'^[0-9]{8,}$', "8+ dígitos consecutivos"),
                    (r'^[dD][A-F0-9]{4,}', "Padrão hexadecimal (dAdBdC)"),
                    (r'[A-Z][a-z][A-Z][a-z][A-Z]', "Padrão alternado suspeito (aBcDeF)"),
                    (r'^[^a-zA-Z]*$', "Somente símbolos/números sem letras"),
                ]
                for pattern, desc in garbage_patterns:
                    if re.search(pattern, text_clean):
                        return True, desc

                # [ERROR] BLOQUEIO 6: Repetição excessiva de caracteres
                if len(text_clean) > 5:
                    unique_chars = len(set(text_clean))
                    total_chars = len(text_clean)
                    # Se <25% caracteres únicos = muito repetitivo
                    if unique_chars < total_chars * 0.25:
                        return True, f"Repetição excessiva ({unique_chars} únicos de {total_chars})"

                # [ERROR] BLOQUEIO 7: Dados gráficos/tiles (padrões específicos)
                tile_patterns = [
                    r'^[a-z]{5,}$',              # ktuwv, ijklm (minúsculas consecutivas)
                    r'^[A-Z][a-z]{1,2}[A-Z]',    # AaBbC (padrão de encoding)
                    r'^\d+[A-Z]+\d+',            # 07A17, 84E86 (códigos)
                ]
                for pattern in tile_patterns:
                    if re.match(pattern, text_clean) and len(text_clean) < 8:
                        return True, "Padrão de dados gráficos/tiles detectado"

                # [ERROR] BLOQUEIO 8: Caracteres de controle invisíveis (mas aceita UTF-8/acentos)
                # Rejeita apenas ASCII < 32 (controle), aceita ASCII 32-126 (imprimível) e >= 128 (UTF-8)
                control_chars = sum(1 for char in text_clean if ord(char) < 32)
                if control_chars > 0:
                    return True, f"{control_chars} caracteres de controle detectados"

                # [OK] SE PASSOU POR TODOS OS FILTROS = PROVAVELMENTE VÁLIDO
                return False, ""  # Válido

            def is_refusal_or_garbage(raw_text, original_text):
                """
                REFUSAL FILTER: Detecta se IA recusou traduzir ou retornou lixo
                Retorna True se devemos DESCARTAR a tradução
                """
                import re
                from difflib import SequenceMatcher

                if not raw_text or not isinstance(raw_text, str):
                    return True

                text_lower = raw_text.lower().strip()

                # Padrões de recusa (IA se recusando a traduzir)
                refusal_patterns = [
                    r'não posso',
                    r'i cannot',
                    r'i can\'t',
                    r'sorry',
                    r'desculpe',
                    r'i apologize',
                    r'peço desculpas',
                    r'i\'m unable',
                    r'não consigo',
                    r'i don\'t',
                    r'eu não',
                ]

                for pattern in refusal_patterns:
                    if re.search(pattern, text_lower):
                        return True  # É recusa, descartar

                # Detecta se IA repetiu instruções do prompt
                instruction_keywords = ['1.', '2.', '3.', 'se o texto', 'if the text', 'instructions']
                if any(keyword in text_lower for keyword in instruction_keywords):
                    return True  # Repetiu instruções, descartar

                # Validação de similaridade: >95% igual ao original = não traduziu
                # Reduzido de 0.8 para 0.95 para aceitar traduções similares válidas
                # IMPORTANTE: faz strip em AMBOS para ignorar espaços no início/fim
                similarity = SequenceMatcher(None, original_text.lower().strip(), text_lower).ratio()
                if similarity > 0.95:
                    return True  # Muito similar, não traduziu de verdade

                return False  # Tradução válida

            def clean_translation(raw_text, original_text):
                """Remove prefixos indesejados preservando variáveis e tags"""
                import re

                if not raw_text or not isinstance(raw_text, str):
                    return original_text

                cleaned = raw_text.strip()

                # Remove prefixos comuns de modelos (case-insensitive)
                prefixes_to_remove = [
                    r'^sure[,:]?\s*',
                    r'^claro[,:]?\s*',
                    r'^here\s+(is|are)\s+(the\s+)?translation[s]?[:\s]*',
                    r'^aqui\s+está?\s+(a\s+)?tradução[:\s]*',
                    r'^translation[:\s]+',
                    r'^tradução[:\s]+',
                ]

                for prefix_pattern in prefixes_to_remove:
                    cleaned = re.sub(prefix_pattern, '', cleaned, flags=re.IGNORECASE)

                # Remove dois-pontos inicial isolado
                cleaned = re.sub(r'^:\s*', '', cleaned)

                # Remove aspas desnecessárias no início e fim
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]
                if cleaned.startswith("'") and cleaned.endswith("'"):
                    cleaned = cleaned[1:-1]

                cleaned = cleaned.strip()

                # Se limpeza removeu tudo, retorna original
                if not cleaned or len(cleaned) < 2:
                    return original_text

                return cleaned

            def translate_single(index, text):
                """Traduz um único texto - ULTRA RESPONSIVO"""
                # Check rápido de interrupção
                if not self._is_running:
                    return index, text

                original_text = text.strip()
                if not original_text:
                    return index, original_text

                # 🛡️ FILTRO DE ENTRADA: Detecta lixo binário ANTES de enviar para IA
                is_garbage, reason = is_binary_garbage(original_text)
                if is_garbage:
                    # LOG DETALHADO: Especifica motivo da rejeição
                    self.log_signal.emit(f"[WARN] Texto '{original_text[:30]}' ignorado. Motivo: {reason} (Filtro Entrada)")
                    return index, original_text

                # === TRADUÇÃO COM RETRY AUTOMÁTICO ===
                MAX_RETRIES = 3
                last_error = None

                for attempt in range(MAX_RETRIES):
                    try:
                        # Check antes de traduzir
                        if not self._is_running:
                            return index, text

                        # Prompt OTIMIZADO com DETECÇÃO DE CONTEXTO
                        # Usa prompts diferentes para menu, diálogo, tutorial, etc
                        text_context = prompt_gen.detect_context(original_text)

                        # System prompt baseado no contexto
                        context_rules = {
                            'menu': (
                                "You are translating a GAME MENU. "
                                "Translate ALL items: START=Iniciar, CONTINUE=Continuar, OPTIONS=Opções, "
                                "EXIT=Sair, SAVE=Salvar, LOAD=Carregar, NEW GAME=Novo Jogo. "
                                "Keep translations SHORT."
                            ),
                            'dialog': (
                                "You are translating CHARACTER DIALOGUE. "
                                "Translate EVERYTHING to Portuguese - NO English words allowed. "
                                "PRESERVE the character's personality (sarcastic, grumpy, angry, funny). "
                                "Use natural Brazilian Portuguese speech."
                            ),
                            'tutorial': (
                                "You are translating a GAME TUTORIAL. "
                                "Translate button instructions: PRESS=Pressione, HOLD=Segure, PUSH=Empurre. "
                                "Be CLEAR and DIRECT. Use imperative form."
                            ),
                            'system': (
                                "You are translating SYSTEM MESSAGES. "
                                "Game Over=Fim de Jogo, Pause=Pausado, Score=Pontuação, "
                                "Lives=Vidas, Time=Tempo, Level=Fase, Continue=Continuar. "
                                "Keep SHORT for display limits."
                            ),
                            'story': (
                                "You are translating GAME STORY/NARRATIVE. "
                                "Use flowing narrative Portuguese. Maintain epic/dramatic tone. "
                                "Translate COMPLETELY - no English words."
                            ),
                        }

                        system_prompt = context_rules.get(text_context, (
                            "You are a professional video game translator. "
                            "Translate ALL text to Brazilian Portuguese. "
                            "NEVER leave any English words. "
                            "Keep ONLY technical codes like {VAR}, [NAME], <0A> unchanged."
                        ))

                        # LLAMA 3.1 FORMAT: Usa tags oficiais do modelo
                        prompt = (
                            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                            f"{system_prompt}\n"
                            f"Output ONLY the translation, nothing else.<|eot_id|>"
                            f"<|start_header_id|>user<|end_header_id|>\n\n"
                            f"Translate to Brazilian Portuguese:\n\n"
                            f"{original_text}<|eot_id|>"
                            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
                        )

                        # Calcula tokens necessários baseado no tamanho do texto
                        # AUMENTADO: textos de diálogo precisam de mais tokens
                        word_count = len(original_text.split())
                        num_predict = max(150, min(word_count * 4 + 100, 500))

                        payload = {
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.1,      # Muito baixa = determinístico
                                "num_predict": num_predict,
                                "top_p": 0.9,
                                "repeat_penalty": 1.1,
                                "num_ctx": 1024,         # Llama precisa mais contexto
                                "stop": ["<|eot_id|>", "<|end_of_text|>", "\n\n\n"]
                            }
                        }

                        # Timeout para Llama 3.1
                        timeout_value = 120 + (word_count * 2)

                        response = requests.post(
                            'http://127.0.0.1:11434/api/generate',
                            json=payload,
                            timeout=timeout_value
                        )

                        if response.status_code == 200:
                            raw_translation = response.json().get('response', '')

                            # REFUSAL FILTER: Detecta recusa ou lixo
                            if is_refusal_or_garbage(raw_translation, original_text):
                                # LOG DETALHADO: Mostra texto e resposta da IA
                                self.log_signal.emit(
                                    f"[WARN] Texto '{original_text[:30]}' ignorado. "
                                    f"Motivo: IA Recusou/Alucinou (Filtro Saída). "
                                    f"Resposta: '{raw_translation[:40]}'"
                                )
                                return index, original_text

                            # Extrai tradução com fallback robusto (NUNCA None)
                            translation = prompt_gen.extract_translation(raw_translation, original_text)

                            # Valida e corrige tradução
                            translation = prompt_gen.validate_and_fix_translation(original_text, translation)

                            # Pós-processamento: remove prefixos indesejados
                            translation = clean_translation(translation, original_text)

                            return index, translation
                        else:
                            # Erro HTTP: tenta novamente
                            last_error = f"HTTP {response.status_code}"
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(2 ** attempt)  # Backoff: 1s, 2s, 4s
                                continue
                            else:
                                self.log_signal.emit(f"[WARN] Texto {index} falhou após {MAX_RETRIES} tentativas: {last_error}")
                                return index, original_text

                    except requests.exceptions.ConnectionError as e:
                        last_error = "Conexão perdida com Ollama"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"🔄 Texto {index}: Tentativa {attempt + 1}/{MAX_RETRIES} - Reconectando...")
                            time.sleep(2 ** attempt)  # Backoff exponencial
                            continue
                        else:
                            self.log_signal.emit(
                                f"[ERROR] Texto {index}: Ollama desconectou após {MAX_RETRIES} tentativas.\n"
                                f"   Verifique se 'ollama serve' ainda está rodando."
                            )
                            return index, original_text

                    except requests.exceptions.Timeout as e:
                        last_error = f"Timeout após 180s"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"⏱️ Texto {index}: Timeout - Tentativa {attempt + 1}/{MAX_RETRIES}")
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            # Fallback: tenta tradução simplificada linha por linha
                            self.log_signal.emit(f"🔄 Texto {index}: Tentando fallback...")
                            try:
                                lines = original_text.split('\n')
                                if len(lines) > 1:
                                    # Texto multi-linha: traduz linha por linha
                                    translated_lines = []
                                    for line in lines:
                                        if not line.strip():
                                            translated_lines.append(line)
                                            continue
                                        # Prompt Llama 3.1 para fallback - FORÇAR TRADUÇÃO COMPLETA
                                        simple_prompt = (
                                            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                                            f"You are a translator. Translate ALL text to Brazilian Portuguese. "
                                            f"Do NOT leave any English words.<|eot_id|>"
                                            f"<|start_header_id|>user<|end_header_id|>\n\n"
                                            f"Translate to Portuguese: {line.strip()}<|eot_id|>"
                                            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
                                        )
                                        simple_payload = {
                                            "model": self.model,
                                            "prompt": simple_prompt,
                                            "stream": False,
                                            "options": {
                                                "temperature": 0.2,
                                                "num_predict": 256,  # AUMENTADO
                                                "num_ctx": 1024,     # AUMENTADO
                                                "stop": ["<|eot_id|>", "\n\n"]
                                            }
                                        }
                                        resp = requests.post(
                                            'http://127.0.0.1:11434/api/generate',
                                            json=simple_payload,
                                            timeout=90
                                        )
                                        if resp.status_code == 200:
                                            raw = resp.json().get('response', '')
                                            # Usa extrator robusto
                                            line_trans = prompt_gen.extract_translation(raw, line)
                                            line_trans = clean_translation(line_trans, line)
                                            translated_lines.append(line_trans)
                                        else:
                                            translated_lines.append(line)
                                    fallback_result = '\n'.join(translated_lines)
                                    self.log_signal.emit(f"[OK] Texto {index}: Fallback OK")
                                    return index, fallback_result
                            except Exception as fb_err:
                                self.log_signal.emit(f"[WARN] Fallback erro: {str(fb_err)[:50]}")

                            # Se fallback falhar: retorna original (não marca UNTRANSLATED)
                            self.log_signal.emit(f"[WARN] Texto {index}: Mantendo original")
                            return index, original_text

                    except requests.exceptions.HTTPError as e:
                        last_error = f"HTTPError: {_sanitize_error(e)}"
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            self.log_signal.emit(f"[WARN] Texto {index}: Erro HTTP - {str(e)[:80]}")
                            return index, original_text

                    except Exception as e:
                        # Erro inesperado: mostra COMPLETO (não apenas 50 chars)
                        error_type = type(e).__name__
                        error_msg = str(e)
                        last_error = f"{error_type}: {error_msg}"

                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(f"[WARN] Texto {index}: {error_type} - Tentativa {attempt + 1}/{MAX_RETRIES}")
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            self.log_signal.emit(
                                f"[ERROR] Texto {index}: ERRO CRÍTICO após {MAX_RETRIES} tentativas:\n"
                                f"   Tipo: {error_type}\n"
                                f"   Detalhe: {error_msg[:200]}"
                            )
                            return index, original_text

                # Fallback final (não deveria chegar aqui)
                return index, original_text

            # Processa textos com UI FLUIDA
            completed = 0
            start_time = time.time()

            self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
            try:
                for batch_start in range(0, len(unique_texts), BATCH_SIZE):
                    # [OK] CHECK FREQUENTE de interrupção
                    if not self._is_running:
                        self.log_signal.emit("[WARN] Tradução interrompida pelo usuário.")
                        break

                    batch_end = min(batch_start + BATCH_SIZE, len(unique_texts))
                    batch = [(i, unique_texts[i]) for i in range(batch_start, batch_end)]

                    # Submete batch
                    futures = {self.executor.submit(translate_single, idx, text): idx for idx, text in batch}

                    # Aguarda resultados COM CHECKS de interrupção
                    for future in as_completed(futures):
                        # [OK] CHECK antes de processar resultado
                        if not self._is_running:
                            break

                        idx, translation = future.result()

                        # VALIDAÇÃO PÓS-TRADUÇÃO: verifica se não é inglês puro
                        original_text = unique_texts[idx]
                        if translation and translation != original_text:
                            # Re-valida com extrator robusto
                            translation = prompt_gen.extract_translation(translation, original_text)
                            translation = prompt_gen.validate_and_fix_translation(original_text, translation)

                        translated_unique[idx] = translation
                        completed += 1

                        # 📺 PAINEL EM TEMPO REAL
                        self.realtime_signal.emit(original_text, translation, "Llama 3.1")

                        # Atualiza progresso
                        percent = int((completed / len(unique_texts)) * 100)
                        self.progress_signal.emit(percent)

                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta_seconds = (len(unique_texts) - completed) / rate if rate > 0 else 0
                        eta_minutes = eta_seconds / 60

                        self.status_signal.emit(f"[START] {completed}/{len(unique_texts)} ({percent}%) | ETA: {eta_minutes:.1f}min")

                        # 🌡️ GPU BREATH: Respiro térmico MÁXIMO para GTX 1060
                        # 1.5s mantém GPU abaixo de 70°C (seguro)
                        time.sleep(1.5)  # PROTEÇÃO TÉRMICA: 1.5s entre traduções

                    # Log a cada batch
                    self.log_signal.emit(f"[OK] Batch {batch_start//BATCH_SIZE + 1}/{(len(unique_texts)+BATCH_SIZE-1)//BATCH_SIZE} completo")

                    # 🌡️ RESPIRO TÉRMICO entre batches (resfriamento intensivo)
                    time.sleep(2.0)  # 2 segundos: GPU resfria antes do próximo batch

            finally:
                # Garante shutdown do executor
                self.executor.shutdown(wait=False)
                self.executor = None

            # === FASE 3: RECONSTRUÇÃO ===
            self.log_signal.emit("="*60)
            self.log_signal.emit("🔧 FASE 3: RECONSTRUÇÃO DAS TRADUÇÕES")
            self.log_signal.emit("="*60)

            # Trata None em translated_unique
            for i in range(len(translated_unique)):
                if translated_unique[i] is None:
                    translated_unique[i] = unique_texts[i]  # Fallback para original

            # Reconstrói lista completa aplicando as traduções
            final_translations = optimizer.reconstruct_translations(
                translated_unique,
                lines,
                index_mapping
            )

            # Salva cache
            optimizer.save_cache()
            self.log_signal.emit(f"💾 Cache salvo: {len(optimizer.cache):,} entradas")

            # === DEBUG: CONTADORES ===
            translated_count = 0
            written_count = 0

            for i, (original, translated) in enumerate(zip(lines, final_translations)):
                if original.strip() != translated.strip():
                    translated_count += 1

            # Salva arquivo - PROTEÇÃO ANTI-CRASH
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in final_translations:
                    f.write(line + '\n')
                    written_count += 1

            self.log_signal.emit(f"[DEBUG] Escritas reais: {written_count}")
            self.log_signal.emit(f"[DEBUG] Linhas traduzidas: {translated_count}")
            self.log_signal.emit(f"[DEBUG] Arquivo: {output_file}")

            total_time = time.time() - start_time
            self.log_signal.emit(f"🎉 Completo em {total_time/60:.1f} minutos!")
            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))
# ================================================================
# BASE DE ASSINATURAS FORENSES (Magic Bytes Database)
# ================================================================
FORENSIC_SIGNATURES = {
    # === GAME ENGINES ===
    b'UnityFS': ('Unity Engine', 'PC_GAME'),
    b'Unity': ('Unity Engine (Legacy)', 'PC_GAME'),
    b'UE4': ('Unreal Engine 4', 'PC_GAME'),
    b'UE3': ('Unreal Engine 3', 'PC_GAME'),
    b'Source Engine': ('Source Engine (Valve)', 'PC_GAME'),
    b'REFPACK': ('RefPack (EA Games)', 'PC_GAME'),
    b'CryEngine': ('CryEngine', 'PC_GAME'),
    b'Gamebryo': ('Gamebryo Engine', 'PC_GAME'),
    b'RPG Maker': ('RPG Maker', 'PC_GAME'),

    # === ARCHIVES & COMPRESSION ===
    b'PK\x03\x04': ('ZIP Archive', 'ARCHIVE'),
    b'Rar!\x1a\x07\x00': ('RAR Archive', 'ARCHIVE'),
    b'Rar!\x1a\x07\x01\x00': ('RAR5 Archive', 'ARCHIVE'),
    b'7z\xBC\xAF\x27\x1C': ('7-Zip Archive', 'ARCHIVE'),
    b'\x1F\x8B': ('GZIP Compressed', 'ARCHIVE'),
    b'BZh': ('BZIP2 Compressed', 'ARCHIVE'),
    b'\xFD7zXZ\x00': ('XZ Compressed', 'ARCHIVE'),

    # === INSTALLERS ===
    b'Inno Setup': ('Inno Setup Installer', 'INSTALLER'),
    b'Nullsoft': ('NSIS Installer (Nullsoft)', 'INSTALLER'),
    b'InstallShield': ('InstallShield Installer', 'INSTALLER'),
    b'MSCF': ('Microsoft Cabinet (CAB)', 'INSTALLER'),
    b'szdd': ('MS Compress (SZDD)', 'INSTALLER'),

    # === CLASSIC GAMES ===
    b'IWAD': ('Doom/Hexen (IWAD)', 'PC_GAME'),
    b'PWAD': ('Doom Mod (PWAD)', 'PC_GAME'),
    b'PAK': ('Quake PAK Archive', 'PC_GAME'),
    b'WAD3': ('Half-Life WAD', 'PC_GAME'),
    b'BSP': ('Quake BSP Map', 'PC_GAME'),

    # === AUDIO/VIDEO (para ignorar) ===
    b'RIFF': ('RIFF Container (AVI/WAV)', 'MEDIA'),
    b'ID3': ('MP3 Audio', 'MEDIA'),
    b'OggS': ('OGG Audio', 'MEDIA'),
    b'\x89PNG': ('PNG Image', 'MEDIA'),
    b'\xFF\xD8\xFF': ('JPEG Image', 'MEDIA'),
    b'GIF8': ('GIF Image', 'MEDIA'),
}


class ChatGPTWorker(QThread):
    """
    Worker para tradução usando OpenAI ChatGPT API.
    Suporta GPT-3.5-turbo e GPT-4.
    """
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    realtime_signal = pyqtSignal(str, str, str)  # original, traduzido, tradutor

    def __init__(self, api_key: str, input_file: str, target_language: str = "Portuguese (Brazil)",
                 model: str = "gpt-3.5-turbo"):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self.model = model
        self._is_running = True

    def stop(self):
        """Para a tradução"""
        self._is_running = False
        self.log_signal.emit("🛑 Parada solicitada - interrompendo...")

    def run(self):
        try:
            import requests
            import time
            import re

            self.log_signal.emit(f"🤖 Iniciando ChatGPT ({self.model})...")
            self.status_signal.emit("Conectando à OpenAI...")

            # Lê arquivo de entrada
            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Filtra linhas com formato [0xOFFSET] texto
            text_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith('[0x') and ']' in line:
                    text_lines.append(line)

            total = len(text_lines)
            if total == 0:
                self.error_signal.emit("Nenhum texto encontrado no arquivo!")
                return

            self.log_signal.emit(f"[STATS] {total} textos para traduzir")

            # Prepara arquivo de saída
            output_file = self.input_file.replace('.txt', '_translated.txt')
            if output_file == self.input_file:
                output_file = self.input_file.replace('.txt', '') + '_translated.txt'

            translated_lines = []
            errors = 0

            # Processa em lotes de 10 para eficiência
            batch_size = 10

            for i in range(0, total, batch_size):
                if not self._is_running:
                    self.log_signal.emit("⏹️ Tradução interrompida pelo usuário")
                    break

                batch = text_lines[i:i + batch_size]
                batch_texts = []

                # Extrai apenas os textos (sem offsets)
                for line in batch:
                    match = re.match(r'^\[0x[0-9a-fA-F]+\]\s*(.*)$', line)
                    if match:
                        batch_texts.append(match.group(1))

                if not batch_texts:
                    continue

                # Monta prompt para ChatGPT
                texts_to_translate = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch_texts)])

                prompt = f"""Translate the following game texts to {self.target_language}.
Keep the same numbering. Keep translations SHORT (same length or shorter than original).
Do NOT add explanations. Only return the translated lines with numbers.

{texts_to_translate}"""

                # Chama API da OpenAI
                try:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }

                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a professional game translator. Keep translations concise and natural."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    }

                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60
                    )

                    if response.status_code == 200:
                        result = response.json()
                        translated_text = result['choices'][0]['message']['content']

                        # Parse das traduções
                        trans_lines = translated_text.strip().split('\n')
                        translations = {}

                        for tl in trans_lines:
                            # Tenta extrair número e texto
                            match = re.match(r'^(\d+)\.\s*(.*)$', tl.strip())
                            if match:
                                idx = int(match.group(1)) - 1
                                translations[idx] = match.group(2)

                        # Combina com offsets originais
                        for j, line in enumerate(batch):
                            offset_match = re.match(r'^(\[0x[0-9a-fA-F]+\])', line)
                            if offset_match:
                                offset = offset_match.group(1)
                                if j in translations:
                                    translated_lines.append(f"{offset} {translations[j]}")
                                    # Emite para painel em tempo real
                                    self.realtime_signal.emit(
                                        batch_texts[j] if j < len(batch_texts) else "",
                                        translations[j],
                                        "ChatGPT"
                                    )
                                else:
                                    # Mantém original se tradução falhou
                                    translated_lines.append(line)
                    else:
                        error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                        self.log_signal.emit(f"[WARN] Erro API: {error_msg}")
                        errors += 1
                        # Mantém originais em caso de erro
                        translated_lines.extend(batch)

                        if "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                            self.log_signal.emit("⏳ Rate limit - aguardando 60s...")
                            time.sleep(60)

                except requests.exceptions.Timeout:
                    self.log_signal.emit("[WARN] Timeout na requisição")
                    errors += 1
                    translated_lines.extend(batch)

                except Exception as e:
                    self.log_signal.emit(f"[WARN] Erro: {_sanitize_error(e)}")
                    errors += 1
                    translated_lines.extend(batch)

                # Atualiza progresso
                progress = int(((i + len(batch)) / total) * 100)
                self.progress_signal.emit(progress)
                self.status_signal.emit(f"Traduzindo... {progress}%")

                # Pequena pausa entre lotes para não exceder rate limit
                time.sleep(0.5)

            # Salva arquivo
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(translated_lines))

            self.log_signal.emit(f"[OK] Tradução concluída: {len(translated_lines)} linhas")
            if errors > 0:
                self.log_signal.emit(f"[WARN] {errors} erros durante tradução")

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")
            self.finished_signal.emit(output_file)

        except Exception as e:
            import traceback
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"[ERROR] Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))


class EngineDetectionWorker(QThread):
    """
    WORKER DE DETECÇÃO DE ENGINE (PERFORMANCE CRÍTICA).
    Thread separada para análise de arquivos gigantes sem travar UI.

    OTIMIZAÇÕES:
    - Lê apenas primeiros 8KB do arquivo (não carrega tudo na RAM)
    - Heurística garantida por extensão/tamanho
    - NUNCA retorna 'Unknown' para extensões conhecidas
    """
    detection_complete = pyqtSignal(dict)  # Emite resultado da detecção
    progress_signal = pyqtSignal(str)      # Status em tempo real

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        """
        SISTEMA DE DNA BINÁRIO - Identificação precisa de plataforma e engine.
        Lê posições específicas do arquivo para criar "Certidão de Nascimento" do jogo.
        """
        try:
            self.progress_signal.emit("🔍 Analisando DNA do arquivo...")

            if not os.path.exists(self.file_path):
                self.detection_complete.emit({
                    'type': 'ERROR',
                    'platform': 'Arquivo não encontrado',
                    'engine': 'N/A',
                    'notes': 'Path inválido',
                    'platform_code': None
                })
                return

            file_ext = os.path.splitext(self.file_path)[1].lower()
            file_size = os.path.getsize(self.file_path)
            file_size_mb = file_size / (1024 * 1024)

            # ================================================================
            # LEITURA OTIMIZADA: Lê apenas setores críticos do arquivo
            # ================================================================
            header = b''
            snes_header_zone = b''  # 0x7FC0 região
            genesis_header_zone = b''  # 0x100 região
            ps1_sector_check = b''

            try:
                with open(self.file_path, 'rb') as f:
                    # Header inicial (primeiros 8KB)
                    f.seek(0)
                    header = f.read(8192)

                    # SNES: Checksum header em 0x7FC0
                    if file_size > 0x8000:
                        f.seek(0x7FC0)
                        snes_header_zone = f.read(64)

                    # Genesis: Verificação de 'SEGA' em 0x100
                    if file_size > 0x200:
                        f.seek(0x100)
                        genesis_header_zone = f.read(256)

                    # PS1: Verificação de setores ISO 9660
                    if file_size > 0x9000:
                        f.seek(0x8000)
                        ps1_sector_check = f.read(2048)

            except Exception as e:
                header = b''

            # ================================================================
            # DETECÇÃO LAYER -1: FORENSIC SIGNATURE SCANNING
            # ================================================================
            # Escaneia assinaturas conhecidas nos primeiros 8KB
            detected_signature = None
            for signature, (engine_name_sig, category) in FORENSIC_SIGNATURES.items():
                if signature in header:
                    detected_signature = (engine_name_sig, category)
                    break

            # Se encontrou assinatura forense, processa
            if detected_signature:
                engine_name_sig, category = detected_signature

                # === INSTALLERS ===
                if category == 'INSTALLER':
                    self.progress_signal.emit(f"🔍 Detectado: {engine_name_sig}")
                    self.progress_signal.emit(f"📦 Instalador detectado - Extração disponível")
                    self.progress_signal.emit(f"💡 DICA: Para melhores resultados, você pode instalar o jogo primeiro")

                    self.detection_complete.emit({
                        'type': 'INSTALLER',
                        'platform': f'Instalador ({engine_name_sig})',
                        'engine': engine_name_sig,
                        'notes': f'Instalador detectado | {file_size_mb:.1f} MB | Extração disponível',
                        'platform_code': 'INSTALLER'
                    })
                    return

                # === GAME ENGINES ===
                elif category == 'PC_GAME':
                    self.progress_signal.emit(f"🎮 Engine Detectada: {engine_name_sig} (Advanced Extraction Active)")

                    # Unity específico
                    if 'Unity' in engine_name_sig:
                        notes = f'Unity Engine | {file_size_mb:.1f} MB | UTF-16LE + Asset Bundles'

                        self.detection_complete.emit({
                            'type': 'PC_GAME',
                            'platform': 'PC (Unity Engine)',
                            'engine': engine_name_sig,
                            'notes': notes,
                            'platform_code': 'PC'
                        })
                        return

                    # Unreal específico
                    elif 'Unreal' in engine_name_sig:
                        notes = f'Unreal Engine | {file_size_mb:.1f} MB | Localization Assets (.uasset)'

                        self.detection_complete.emit({
                            'type': 'PC_GAME',
                            'platform': 'PC (Unreal Engine)',
                            'engine': engine_name_sig,
                            'notes': notes,
                            'platform_code': 'PC'
                        })
                        return

                    # Doom/Quake
                    elif 'Doom' in engine_name_sig or 'Quake' in engine_name_sig:
                        notes = f'{engine_name_sig} | {file_size_mb:.1f} MB | WAD/PAK Extraction'

                        self.detection_complete.emit({
                            'type': 'PC_GAME',
                            'platform': 'PC (Classic FPS)',
                            'engine': engine_name_sig,
                            'notes': notes,
                            'platform_code': 'PC'
                        })
                        return

                # === ARCHIVES ===
                elif category == 'ARCHIVE':
                    self.progress_signal.emit(f"📦 Detectado: {engine_name_sig}")
                    self.progress_signal.emit(f"💡 Extraia o arquivo primeiro e selecione o jogo")

                    self.detection_complete.emit({
                        'type': 'ARCHIVE',
                        'platform': f'Arquivo Compactado ({engine_name_sig})',
                        'engine': engine_name_sig,
                        'notes': f'Arquivo compactado | {file_size_mb:.1f} MB | Extraia primeiro',
                        'platform_code': 'ARCHIVE'
                    })
                    return

                # === MEDIA FILES (ignorar) ===
                elif category == 'MEDIA':
                    self.progress_signal.emit(f"[WARN] Arquivo de mídia detectado: {engine_name_sig}")

                    self.detection_complete.emit({
                        'type': 'MEDIA',
                        'platform': 'Arquivo de Mídia (não é jogo)',
                        'engine': engine_name_sig,
                        'notes': f'Arquivo de mídia | {file_size_mb:.1f} MB | Não contém textos traduzíveis',
                        'platform_code': 'MEDIA'
                    })
                    return

            # ================================================================
            # DETECÇÃO LAYER 0: PRIORIDADE ABSOLUTA - EXTENSÃO .EXE
            # ================================================================
            # REGRA CRÍTICA: .exe SEMPRE é Windows, não importa bytes internos
            if file_ext in ['.exe', '.dll', '.scr']:
                category = "High Capacity" if file_size_mb > 100 else "Medium Size" if file_size_mb > 10 else "Small"

                pe_info = "Windows Executable"
                engine_name = f'Windows Executable ({category})'
                notes = f'{pe_info} | {file_size_mb:.1f} MB'

                # Valida PE header se possível
                if header[0:2] == b'MZ':
                    try:
                        if len(header) > 0x3C + 4:
                            pe_offset = int.from_bytes(header[0x3C:0x3C+4], 'little')
                            if pe_offset < len(header) - 4 and header[pe_offset:pe_offset+4] == b'PE\x00\x00':
                                pe_info = "Win32 PE Confirmed"
                                notes = f'{pe_info} | {file_size_mb:.1f} MB'
                    except:
                        pass

                # Detecta DarkStone especificamente
                if b'DarkStone' in header or b'DARKSTONE' in header or b'jeRaff' in header:
                    engine_name = 'DarkStone Original (Delphine Software)'
                    notes = f'Action RPG ({file_size_mb:.1f} MB) | Desenvolvido em 1999'

                self.detection_complete.emit({
                    'type': 'PC_GAME',
                    'platform': 'PC (Windows)',
                    'engine': engine_name,
                    'notes': notes,
                    'platform_code': 'PC'
                })
                return

            # ================================================================
            # DETECÇÃO LAYER 1: DNA BINÁRIO COM LIMITES DE SANIDADE
            # ================================================================

            # ═══ SUPER NINTENDO (SNES) ═══
            # TRAVA DE SANIDADE: SNES real nunca ultrapassa 12MB
            if file_ext in ['.smc', '.sfc'] and file_size_mb <= 12:
                # Verifica checksum válido em 0x7FDC-0x7FDD
                is_valid_snes = False
                rom_name = "SNES ROM"

                if len(snes_header_zone) >= 64:
                    # Checksum complement em 0x7FDC
                    checksum = snes_header_zone[0x1C:0x1E]
                    complement = snes_header_zone[0x1E:0x20]

                    # ROM title em 0x7FC0-0x7FD4
                    title_bytes = snes_header_zone[0:21]
                    try:
                        rom_name = title_bytes.decode('ascii', errors='ignore').strip()
                        if not rom_name or len(rom_name) < 3:
                            rom_name = "SNES ROM"
                    except:
                        rom_name = "SNES ROM"

                    # Valida checksums
                    if len(checksum) == 2 and len(complement) == 2:
                        chk_val = int.from_bytes(checksum, 'little')
                        cmp_val = int.from_bytes(complement, 'little')
                        if (chk_val ^ cmp_val) == 0xFFFF:
                            is_valid_snes = True

                detection_note = f"ROM Title: {rom_name}" if is_valid_snes else f"Console 16-bit ({file_size_mb:.1f} MB)"

                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'Super Nintendo (16-bit)',
                    'engine': 'SNES Cartridge',
                    'notes': detection_note,
                    'platform_code': 'SNES'
                })
                return

            # ═══ SEGA GENESIS / MEGA DRIVE ═══
            # TRAVA DE SANIDADE: Genesis real nunca ultrapassa 8MB
            if (file_ext in ['.md', '.gen', '.smd'] and file_size_mb <= 8) or (b'SEGA' in genesis_header_zone[:16] and file_size_mb <= 8):
                rom_name = "Genesis ROM"

                # Tenta extrair nome do jogo em 0x150
                if len(genesis_header_zone) >= 200:
                    try:
                        title_bytes = genesis_header_zone[0x50:0x90]  # Domestic name
                        rom_name = title_bytes.decode('ascii', errors='ignore').strip()
                        if not rom_name or len(rom_name) < 3:
                            rom_name = "Genesis ROM"
                    except:
                        rom_name = "Genesis ROM"

                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'Mega Drive / Genesis (16-bit)',
                    'engine': 'Sega Console',
                    'notes': f"ROM Title: {rom_name}",
                    'platform_code': 'GENESIS'
                })
                return

            # ═══ PLAYSTATION 1 (CD-ROM) ═══
            if b'CD001' in ps1_sector_check or (file_ext in ['.iso', '.img', '.bin', '.cue'] and file_size_mb > 600):
                # Detecta se é CD ISO 9660
                is_iso9660 = b'CD001' in ps1_sector_check

                detection_note = "CD-ROM Image (ISO 9660)" if is_iso9660 else f"Disc Image ({file_size_mb:.0f} MB)"

                # Tenta detectar jogo específico no header
                game_signature = "PlayStation 1 Game"
                if b'SLUS' in header or b'SCES' in header or b'SCUS' in header:
                    game_signature = "PS1 Licensed Title"

                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'PlayStation 1 (CD-ROM)',
                    'engine': game_signature,
                    'notes': detection_note,
                    'platform_code': 'PS1'
                })
                return

            # ═══ NINTENDO NES ═══
            # TRAVA DE SANIDADE: NES real nunca ultrapassa 2MB
            if (header[0:4] == b'NES\x1a' or file_ext == '.nes') and file_size_mb <= 2:
                # iNES header contém informações
                prg_rom_size = 0
                chr_rom_size = 0
                mapper = 0

                if len(header) >= 16 and header[0:4] == b'NES\x1a':
                    prg_rom_size = header[4] * 16  # KB
                    chr_rom_size = header[5] * 8   # KB
                    mapper = ((header[6] >> 4) & 0x0F) | (header[7] & 0xF0)

                    notes = f"Mapper: {mapper} | PRG: {prg_rom_size}KB | CHR: {chr_rom_size}KB"
                else:
                    notes = f"Console 8-bit ({file_size_mb:.1f} MB)"

                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'Nintendo Entertainment System (8-bit)',
                    'engine': 'NES iNES Format',
                    'notes': notes,
                    'platform_code': 'NES'
                })
                return

            # ================================================================
            # DETECÇÃO LAYER 2: ENGINES DE PC (DNA de Software)
            # ================================================================

            # ═══ DOOM / HEXEN (WAD Files) ═══
            if header[0:4] in (b'IWAD', b'PWAD'):
                wad_type = "Internal WAD" if header[0:4] == b'IWAD' else "Patch WAD"
                num_lumps = 0
                if len(header) >= 12:
                    num_lumps = int.from_bytes(header[4:8], 'little')

                self.detection_complete.emit({
                    'type': 'PC_GAME',
                    'platform': 'PC (DOS/Windows)',
                    'engine': 'id Tech 1 (Doom Engine)',
                    'notes': f"{wad_type} | {num_lumps} lumps",
                    'platform_code': 'PC'
                })
                return

            # ═══ UNITY ENGINE ═══
            if b'UnityFS' in header[:512] or b'UnityWeb' in header[:512] or b'UnityRaw' in header[:512]:
                unity_version = "Unknown"

                # Tenta extrair versão do Unity
                if b'UnityFS' in header:
                    try:
                        # Versão geralmente aparece após "UnityFS"
                        version_section = header[header.find(b'UnityFS'):header.find(b'UnityFS')+100]
                        if b'201' in version_section or b'202' in version_section:
                            unity_version = "2017-2024"
                    except:
                        pass

                self.detection_complete.emit({
                    'type': 'PC_GAME',
                    'platform': 'PC (Unity Engine)',
                    'engine': f'Unity {unity_version}',
                    'notes': f'Modern game engine ({file_size_mb:.1f} MB)',
                    'platform_code': 'PC'
                })
                return

            # ═══ UNREAL ENGINE ═══
            if header[0:4] == b'\xC1\x83\x2A\x9E' or b'Unreal' in header[:512]:
                self.detection_complete.emit({
                    'type': 'PC_GAME',
                    'platform': 'PC (Unreal Engine)',
                    'engine': 'Unreal Engine',
                    'notes': f'AAA game engine ({file_size_mb:.1f} MB)',
                    'platform_code': 'PC'
                })
                return

            # ═══ WINDOWS PE EXECUTABLES (Generic) ═══
            if header[0:2] == b'MZ' and file_ext in ['.exe', '.dat']:
                # Analisa tamanho para categorizar
                if file_size_mb > 100:
                    category = "High Capacity"
                elif file_size_mb > 10:
                    category = "Medium Size"
                else:
                    category = "Small"

                # Tenta extrair info do PE header
                pe_info = "Win32 PE"
                try:
                    if len(header) > 0x3C + 4:
                        pe_offset = int.from_bytes(header[0x3C:0x3C+4], 'little')
                        if pe_offset < len(header) - 4:
                            pe_signature = header[pe_offset:pe_offset+4]
                            if pe_signature == b'PE\x00\x00':
                                pe_info = "Win32 PE Confirmed"
                except:
                    pass

                self.detection_complete.emit({
                    'type': 'PC_GAME',
                    'platform': 'PC (Windows)',
                    'engine': f'Windows Executable ({category})',
                    'notes': f'{pe_info} | {file_size_mb:.1f} MB',
                    'platform_code': 'PC'
                })
                return

            # ================================================================
            # DETECÇÃO LAYER 3: Fallback por extensão
            # ================================================================

            # Game Boy / GBA
            if file_ext in ['.gb', '.gbc']:
                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'Game Boy / Game Boy Color (8-bit)',
                    'engine': 'Nintendo Handheld',
                    'notes': f'Portátil ({file_size_mb:.1f} MB)',
                    'platform_code': 'GB'
                })
                return

            if file_ext == '.gba':
                self.detection_complete.emit({
                    'type': 'ROM',
                    'platform': 'Game Boy Advance (32-bit)',
                    'engine': 'Nintendo Handheld Advanced',
                    'notes': f'Portátil avançado ({file_size_mb:.1f} MB)',
                    'platform_code': 'GBA'
                })
                return

            # Fallback genérico
            self.detection_complete.emit({
                'type': 'GENERIC',
                'platform': f'Arquivo {file_ext.upper()[1:] if file_ext else "Binário"}',
                'engine': f'Binary File ({file_size_mb:.1f} MB)',
                'notes': 'Sistema fará melhor esforço na extração',
                'platform_code': None
            })

        except Exception as e:
            import traceback
            self.detection_complete.emit({
                'type': 'ERROR',
                'platform': 'Erro ao analisar',
                'engine': 'N/A',
                'notes': f'{_sanitize_error(e)} | {_sanitize_error(traceback.format_exc()[:200])}',
                'platform_code': None
            })


class ReinsertionWorker(QThread):
    """Worker dedicado para Reinserção. Thread-safe."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, rom_path: str, translated_path: str, output_rom_path: str):
        super().__init__()
        self.rom_path = rom_path
        self.translated_path = translated_path
        self.output_rom_path = output_rom_path

    def run(self):
        try:
            self.status_signal.emit("Preparando arquivos...")
            self.progress_signal.emit(0)

            # ================================================================
            # DETECÇÃO AUTOMÁTICA: PC Game / Sega / ROM de Console
            # ================================================================
            file_ext = os.path.splitext(self.rom_path)[1].lower()

            if file_ext in ['.exe', '.dll', '.dat']:
                # Usa módulo PC Reinserter
                self.log_signal.emit("🖥️ Detectado: PC Game - usando PC Reinserter")
                self._reinsert_pc_game()
                return
            elif file_ext in ['.sms', '.md', '.gen', '.smd']:
                # Usa módulo Sega Reinserter
                self.log_signal.emit("🎮 Detectado: Sega ROM - usando Sega Reinserter")
                self._reinsert_sega_rom()
                return
            else:
                # Usa módulo ROM tradicional
                self.log_signal.emit("🎮 Detectado: Console ROM - usando reinserção tradicional")

            with open(self.translated_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            shutil.copyfile(self.rom_path, self.output_rom_path)

            rom_size = os.path.getsize(self.output_rom_path)

            with open(self.output_rom_path, 'r+b') as rom_file:
                total_lines = len(lines)

                for i, line in enumerate(lines):
                    if self.isInterruptionRequested():
                        self.log_signal.emit("Reinserção interrompida pelo usuário.")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('['):
                        try:
                            match = re.match(r'^\[(0x[0-9a-fA-F]+)\]\s*(.*)$', line)
                            if match:
                                offset_str = match.group(1)
                                offset = int(offset_str, 16)
                                new_text_with_codes = match.group(2)

                                # Validação de offset
                                if offset < 0 or offset >= rom_size:
                                    self.log_signal.emit(
                                        f"[WARN] Offset inválido {offset_str} na linha {i+1}. "
                                        f"ROM tem {rom_size} bytes. Pulando."
                                    )
                                    continue

                                rom_file.seek(offset)

                                # AVISO CRÍTICO: Encoding
                                # Latin-1 é usado aqui, mas ROMs geralmente usam tabelas
                                # customizadas. Acentos podem ser corrompidos.
                                # Idealmente, use um mapeamento de caracteres específico da ROM.
                                encoded_text = new_text_with_codes.encode('latin-1', errors='ignore')

                                # Validação de tamanho (básica)
                                if len(encoded_text) > 100:
                                    self.log_signal.emit(
                                        f"[WARN] Texto muito longo na linha {i+1} "
                                        f"({len(encoded_text)} bytes). "
                                        f"Pode sobrescrever dados importantes."
                                    )

                                rom_file.write(encoded_text)

                        except ValueError as e:
                            self.log_signal.emit(
                                f"[WARN] Erro de offset hexadecimal na linha {i+1}: {_sanitize_error(e)}. Pulando."
                            )
                            continue
                        except Exception as e:
                            self.log_signal.emit(
                                f"[WARN] Erro de escrita na linha {i+1} "
                                f"({line[:50]}...): {_sanitize_error(e)}. Pulando."
                            )
                            continue

                    # Atualização de progresso mais frequente
                    if total_lines > 0 and (i % 20 == 0 or i == total_lines - 1):
                        percent = int((i / total_lines) * 90)  # Deixa 10% para checksum
                        self.status_signal.emit(f"Reinserindo... {percent}%")
                        self.progress_signal.emit(percent)

            # ============================================================
            # [OK] KERNEL V 9.5: CHECKSUM FIXER (LACRE DE COMPATIBILIDADE)
            # ============================================================
            # CRÍTICO: Hardware SNES real exige checksum válido
            self.status_signal.emit("🔐 Recalculando checksum SNES...")
            self.progress_signal.emit(95)
            self._fix_snes_checksum(self.output_rom_path)

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")
            self.log_signal.emit(
                f"[OK] ROM salva com sucesso: {os.path.basename(self.output_rom_path)}"
            )
            self.finished_signal.emit()

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))

    def _fix_snes_checksum(self, rom_path: str):
        """
        [OK] KERNEL V 9.5: CHECKSUM FIXER (LACRE DE COMPATIBILIDADE)

        Recalcula e corrige o checksum SNES no header interno.
        CRÍTICO para funcionamento em hardware real (SNES/Everdrive/flashcarts).

        Args:
            rom_path: Caminho do arquivo ROM a corrigir
        """
        try:
            with open(rom_path, 'r+b') as f:
                rom_data = bytearray(f.read())
                rom_size = len(rom_data)

                # Detecta se tem header SMC (512 bytes)
                has_header = (rom_size % 1024 == 512)
                header_offset = 0x200 if has_header else 0x000

                # Detecta tipo de mapeamento (LoROM vs HiROM)
                map_mode_offset = 0x7FD5 + header_offset
                if map_mode_offset < rom_size:
                    map_mode = rom_data[map_mode_offset]
                    is_hirom = (map_mode in [0x21, 0x31])
                else:
                    is_hirom = False

                # Define offset do checksum
                if is_hirom:
                    checksum_offset = 0xFFDC + header_offset
                else:
                    checksum_offset = 0x7FDC + header_offset

                # Valida offset
                if checksum_offset + 4 > rom_size:
                    self.log_signal.emit(f"[WARN] ROM muito pequena para checksum SNES")
                    return

                # Calcula checksum (16-bit sum)
                checksum = 0
                for i in range(rom_size):
                    if checksum_offset <= i < checksum_offset + 4:
                        continue
                    checksum += rom_data[i]

                checksum = checksum & 0xFFFF
                complement = (0xFFFF - checksum) & 0xFFFF

                # Grava checksum no header
                rom_data[checksum_offset + 0] = complement & 0xFF
                rom_data[checksum_offset + 1] = (complement >> 8) & 0xFF
                rom_data[checksum_offset + 2] = checksum & 0xFF
                rom_data[checksum_offset + 3] = (checksum >> 8) & 0xFF

                # Salva ROM com checksum corrigido
                f.seek(0)
                f.write(rom_data)

                map_type = "HiROM" if is_hirom else "LoROM"
                self.log_signal.emit(
                    f"🔐 Checksum SNES corrigido: 0x{checksum:04X} / "
                    f"Complemento: 0x{complement:04X} ({map_type})"
                )

        except Exception as e:
            self.log_signal.emit(f"[WARN] Erro ao corrigir checksum: {_sanitize_error(e)}")

    def _reinsert_pc_game(self):
        """
        Reinserção específica para PC Games (.exe).
        Usa módulo pc_game_reinserter.py
        """
        try:
            # Import do módulo PC
            from pc_game_reinserter import reinsert_pc_game

            # Callback para progresso
            def progress_callback(percent, message):
                self.progress_signal.emit(percent)
                self.status_signal.emit(message)
                self.log_signal.emit(message)

            # Executa reinserção PC
            result = reinsert_pc_game(
                self.rom_path,
                self.translated_path,
                self.output_rom_path,
                progress_callback
            )

            if result['success']:
                self.log_signal.emit(f"\n{'='*60}")
                self.log_signal.emit(f"[OK] REINSERÇÃO PC CONCLUÍDA!")
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit(f"[STATS] Estatísticas de Processamento:")
                self.log_signal.emit(f"   • Strings inseridas: {result['modified']}")
                self.log_signal.emit(f"   • Strings realocadas: {result.get('relocated', 0)}")
                self.log_signal.emit(f"   • Strings ignoradas: {result['skipped']}")
                self.log_signal.emit(f"   • Expansão do arquivo: +{result.get('expansion', 0):,} bytes")

                # Estatísticas de ponteiros
                if 'pointer_stats' in result:
                    pstats = result['pointer_stats']
                    self.log_signal.emit(f"\n🔗 Análise de Ponteiros:")
                    self.log_signal.emit(f"   • Realocações com ponteiros: {pstats.get('relocated_with_pointers', 0)}")
                    self.log_signal.emit(f"   • Realocações sem ponteiros: {pstats.get('relocated_no_pointers', 0)}")
                    self.log_signal.emit(f"   • Taxa de detecção: {pstats.get('pointer_detection_rate', 0):.1f}%")

                    if pstats.get('relocated_no_pointers', 0) > 0:
                        self.log_signal.emit(f"\nℹ️  NOTA: Strings sem ponteiros detectados podem ser:")
                        self.log_signal.emit(f"   • Strings inline (não referenciadas por ponteiros)")
                        self.log_signal.emit(f"   • Dados de interface hard-coded")
                        self.log_signal.emit(f"   • Recursos estáticos do jogo")

                if result.get('errors'):
                    self.log_signal.emit(f"\n[WARN] Primeiros erros detectados:")
                    for error in result['errors'][:5]:
                        self.log_signal.emit(f"  • {error}")

                self.log_signal.emit(f"{'='*60}\n")
                self.finished_signal.emit()
            else:
                self.error_signal.emit(result.get('error', 'Erro desconhecido'))

        except ImportError:
            self.error_signal.emit("Módulo pc_game_reinserter não encontrado. Reinstale o software.")
        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Erro PC Reinserter: {error_details}")
            self.error_signal.emit(_sanitize_error(e))

    def _reinsert_sega_rom(self):
        """
        Reinserção específica para Sega ROMs (Master System, Mega Drive).
        Usa módulo sega_reinserter.py
        """
        try:
            # Tenta importar do caminho relativo
            import sys
            current_dir = os.path.dirname(os.path.abspath(__file__))
            core_dir = os.path.join(os.path.dirname(current_dir), "core")
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)

            from sega_reinserter import SegaReinserter

            self.status_signal.emit("Carregando ROM Sega...")
            self.progress_signal.emit(10)

            # Cria reinsertor
            reinserter = SegaReinserter(self.rom_path)

            self.status_signal.emit("Carregando traduções...")
            self.progress_signal.emit(30)

            if (
                str(self.translated_path).lower().endswith(".jsonl")
                and run_qa_gate is not None
            ):
                try:
                    translated_p = Path(self.translated_path)
                    pure_candidates = [
                        translated_p.with_name(
                            translated_p.name.replace("_translated.jsonl", "_pure_text.jsonl")
                        ),
                        translated_p.with_name(
                            translated_p.name.replace(".jsonl", "_pure_text.jsonl")
                        ),
                        translated_p.parent.parent
                        / "1_extracao"
                        / translated_p.name.replace("_translated.jsonl", "_pure_text.jsonl"),
                    ]
                    pure_jsonl = None
                    for cand in pure_candidates:
                        if cand.exists() and cand.is_file():
                            pure_jsonl = str(cand)
                            break
                    mapping_json = None
                    if pure_jsonl:
                        pure_p = Path(pure_jsonl)
                        map_cand = pure_p.with_name(
                            pure_p.name.replace("_pure_text.jsonl", "_reinsertion_mapping.json")
                        )
                        if map_cand.exists() and map_cand.is_file():
                            mapping_json = str(map_cand)

                        if run_autoretry_for_translation is not None:
                            qa_res = run_autoretry_for_translation(
                                pure_jsonl_path=pure_jsonl,
                                translated_jsonl_path=self.translated_path,
                                mapping_json_path=mapping_json,
                                max_retries=max(
                                    1,
                                    min(
                                        10,
                                        int(
                                            os.environ.get("NEUROROM_AUTORETRY_MAX", "3")
                                            or "3"
                                        ),
                                    ),
                                ),
                            )
                            qa_obj = (
                                qa_res.get("qa_gate", {})
                                if isinstance(qa_res, dict)
                                else {}
                            )
                        else:
                            qa_obj = run_qa_gate(
                                pure_jsonl_path=pure_jsonl,
                                translated_jsonl_path=self.translated_path,
                                mapping_json_path=mapping_json,
                                stage="pre_reinsertion",
                            )
                        self.log_signal.emit(
                            "[QA_GATE] pré-reinserção: "
                            f"pass={str(bool(qa_obj.get('pass', False))).lower()} "
                            f"failed={json.dumps(qa_obj.get('failed_checks', []), ensure_ascii=False)}"
                        )
                except Exception as qa_err:
                    self.log_signal.emit(
                        f"[WARN] QA_GATE pré-reinserção falhou: {_sanitize_error(qa_err)}"
                    )

            # Carrega traduções
            translations = reinserter.load_translations(self.translated_path)

            if not translations:
                self.error_signal.emit("Nenhuma tradução encontrada no arquivo")
                return

            self.log_signal.emit(f"[STATS] {len(translations)} textos para reinserir")
            self.status_signal.emit(f"Reinserindo {len(translations)} textos...")
            self.progress_signal.emit(50)

            # Executa reinserção
            success, message = reinserter.reinsert(
                translations,
                self.output_rom_path,
                create_backup=True
            )

            self.progress_signal.emit(90)

            if success:
                self.log_signal.emit(f"\n{'='*60}")
                self.log_signal.emit(f"[OK] REINSERÇÃO SEGA CONCLUÍDA!")
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit(f"[STATS] Estatísticas:")
                self.log_signal.emit(f"   • Inseridos: {reinserter.stats['inserted']}")
                self.log_signal.emit(f"   • Truncados: {reinserter.stats['truncated']}")
                self.log_signal.emit(f"   • Ignorados: {reinserter.stats['skipped']}")
                self.log_signal.emit(f"📂 Arquivo: {os.path.basename(self.output_rom_path)}")
                self.log_signal.emit(f"{'='*60}\n")

                self.progress_signal.emit(100)
                self.status_signal.emit("Concluído!")
                self.finished_signal.emit()
            else:
                self.error_signal.emit(message)

        except ImportError as e:
            self.log_signal.emit(f"[WARN] Erro de importação: {_sanitize_error(e)}")
            self.error_signal.emit("Módulo sega_reinserter não encontrado. Reinstale o software.")
        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Erro Sega Reinserter: {error_details}")
            self.error_signal.emit(_sanitize_error(e))


# --- CONFIG E UTILITÁRIOS ---

class ProjectConfig:
    BASE_DIR = Path(__file__).parent
    ROMS_DIR = BASE_DIR.parent / "ROMs"

    # Diretórios de saída (extração)
    FRAMEWORK_DIR = BASE_DIR.parent  # rom-translation-framework
    CORE_DIR = FRAMEWORK_DIR / 'core'
    EXTRACTION_DIR = CORE_DIR  # compat: algumas rotas usam ProjectConfig.EXTRACTION_DIR
    SCRIPTS_DIR = BASE_DIR.parent / "Scripts principais"
    CONFIG_FILE = BASE_DIR / "translator_config.json"
    I18N_DIR = BASE_DIR.parent / "i18n"
    # --- COLE AQUI (Mantenha o recuo/indentação igual ao de cima) ---

    # Plataformas ordenadas por ano de lançamento
    PLATFORMS = {
        # --- 1977 ---
        "Atari 2600 (1977)": {"code": "atari", "ready": False, "label": "platform_atari"},
        # --- 1983 ---
        "Nintendo (NES) (1983)": {"code": "nes", "ready": False, "label": "platform_nes"},
        # --- 1985 ---
        "Sega Master System (1985)": {"code": "sms", "ready": True, "label": "platform_sms"},
        # --- 1988 ---
        "Sega Mega Drive (1988)": {"code": "md", "ready": False, "label": "platform_md"},
        # --- 1989 ---
        "Game Boy (1989)": {"code": "gb", "ready": False, "label": "platform_gb"},
        # --- 1990 ---
        "Super Nintendo (SNES) (1990)": {"code": "snes", "ready": False, "label": "platform_snes"},
        "Neo Geo (1990)": {"code": "neo", "ready": False, "label": "platform_neo"},
        # --- 1991 ---
        "Sega CD (1991)": {"code": "scd", "ready": False, "label": "platform_scd"},
        # --- 1994 ---
        "PlayStation 1 (PS1) (1994)": {"code": "ps1", "ready": False, "label": "platform_ps1"},
        "Sega Saturn (1994)": {"code": "sat", "ready": False, "label": "platform_sat"},
        # --- 1996 ---
        "Nintendo 64 (N64) (1996)": {"code": "n64", "ready": False, "label": "platform_n64"},
        # --- 1998 ---
        "Game Boy Color (GBC) (1998)": {"code": "gbc", "ready": False, "label": "platform_gbc"},
        "Sega Dreamcast (1998)": {"code": "dc", "ready": False, "label": "platform_dc"},
        # --- 2000 ---
        "PlayStation 2 (PS2) (2000)": {"code": "ps2", "ready": False, "label": "platform_ps2"},
        # --- 2001 ---
        "Game Boy Advance (GBA) (2001)": {"code": "gba", "ready": False, "label": "platform_gba"},
        "Nintendo GameCube (2001)": {"code": "gc", "ready": False, "label": "platform_gc"},
        "Xbox Clássico (2001)": {"code": "xbox", "ready": False, "label": "platform_xbox"},
        # --- 2004 ---
        "Nintendo DS (NDS) (2004)": {"code": "nds", "ready": False, "label": "platform_nds"},
        # --- 2005 ---
        "Xbox 360 (2005)": {"code": "x360", "ready": False, "label": "platform_x360"},
        # --- 2006 ---
        "PlayStation 3 (PS3) (2006)": {"code": "ps3", "ready": False, "label": "platform_ps3"},
        "Nintendo Wii (2006)": {"code": "wii", "ready": False, "label": "platform_wii"},
        # --- 2011 ---
        "Nintendo 3DS (2011)": {"code": "3ds", "ready": False, "label": "platform_3ds"},
        # --- 2012 ---
        "Nintendo Wii U (2012)": {"code": "wiiu", "ready": False, "label": "platform_wiiu"},
        # --- 2013 ---
        "PlayStation 4 (PS4) (2013)": {"code": "ps4", "ready": False, "label": "platform_ps4"},
        # --- 2017 ---
        "Nintendo Switch (2017)": {"code": "switch", "ready": False, "label": "platform_switch"},
        # --- 2020 ---
        "PlayStation 5 (PS5) (2020)": {"code": "ps5", "ready": False, "label": "platform_ps5"},
        # --- PC ---
        "MS-DOS (PC Antigo)": {"code": "dos", "ready": False, "label": "platform_dos"},
        "PC Games (Windows)": {"code": "pc", "ready": False, "label": "platform_pc"},
        "PC Games (Linux)": {"code": "linux", "ready": False, "label": "platform_linux"},
        "PC Games (Mac)": {"code": "mac", "ready": False, "label": "platform_mac"}
    }

    UI_LANGUAGES = {
            "🇧🇷 Português (Brasil)": "pt",
            "🇺🇸 English (US)": "en",
            "🇪🇸 Español (España)": "es",
            "🇫🇷 Français (France)": "fr",
            "🇩🇪 Deutsch (Deutschland)": "de",
            "🇮🇹 Italiano (Italia)": "it",
            "🇯🇵 日本語 (Japanese)": "ja",
            "🇰🇷 한국어 (Korean)": "ko",
            "🇨🇳 中文 (Chinese)": "zh",
            "🇷🇺 Русский (Russian)": "ru",
            "🇸🇦 العربية (Arabic)": "ar",
            "🇮🇳 हिन्दी (Hindi)": "hi",
            "🇹🇷 Türkçe (Turkish)": "tr",
            "🇵🇱 Polski (Polish)": "pl",
            "🇳🇱 Nederlands (Dutch)": "nl"
        }

    FONT_FAMILIES = {
            "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
            "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
            "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
            "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
            "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
            "Arial": "Arial, sans-serif"
        }

    SOURCE_LANGUAGES = {
            "AUTO-DETECTAR": "auto",
            "Japonês (日本語)": "ja",
            "Inglês (English)": "en",
            "Espanhol (Español)": "es",
            "Russo (Русский)": "ru",
            "Chinês Simplificado (简体)": "zh-cn",
            "Chinês Tradicional (繁體)": "zh-tw",
            "Coreano (한국어)": "ko",
            "Francês (Français)": "fr",
            "Alemão (Deutsch)": "de",
            "Italiano (Italiano)": "it",
            "Árabe (العربية)": "ar",
            "Hindi (हिन्दी)": "hi",
            "Turco (Türkçe)": "tr",
            "Polonês (Polski)": "pl"
        }

    TARGET_LANGUAGES = {
            "Português (PT-BR)": "pt",
            "English (US)": "en",
            "Español (ES)": "es",
            "Français (FR)": "fr",
            "Deutsch (DE)": "de",
            "Italiano (IT)": "it",
            "日本語 (Japanese)": "ja",
            "한국어 (Korean)": "ko",
            "中文 (Chinese)": "zh",
            "Русский (Russian)": "ru"
        }
    THEMES = {
            "Preto (Black)": {"window": "#0d0d0d", "text": "#ffffff", "button": "#1a1a1a", "accent": "#4a9eff"},
            "Cinza (Gray)": {"window": "#2d2d2d", "text": "#ffffff", "button": "#3d3d3d", "accent": "#5c9eff"},
            "Branco (White)": {"window": "#f0f0f0", "text": "#000000", "button": "#e1e1e1", "accent": "#308cc6"}
        }

    # Mapping between internal theme keys and translation keys
    THEME_TRANSLATION_KEYS = {
            "Preto (Black)": "theme_black",
            "Cinza (Gray)": "theme_gray",
            "Branco (White)": "theme_white"
        }

    @classmethod
    def ensure_directories(cls):
        cls.ROMS_DIR.mkdir(exist_ok=True, parents=True)
        cls.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # i18n: JSON Loader with fallback
    _translations_cache = {}

    @classmethod
    def load_translations(cls, lang_code: str) -> Dict:
        """
        Load translations from JSON file with caching.
        Fallback hierarchy: requested lang → en → empty dict
        """
        if lang_code in cls._translations_cache:
            return cls._translations_cache[lang_code]

        json_file = cls.I18N_DIR / f"{lang_code}.json"

        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    cls._translations_cache[lang_code] = translations
                    return translations
            except Exception as e:
                print(f"[WARN] Failed to load {lang_code}.json: {_sanitize_error(e)}")

        # Fallback to English if not 'en' itself
        if lang_code != "en":
            return cls.load_translations("en")

        return {}

    # ROADMAP: Future platforms (not shown in main dropdown)
    PLATFORMS_ROADMAP = {
        "PlayStation": ["PS2", "PS3", "PS4", "PS5"],
        "Nintendo Classic": ["NES", "N64", "GameCube", "Wii", "Wii U", "Switch"],
        "Nintendo Portable": ["Game Boy", "Game Boy Color", "Game Boy Advance", "Nintendo DS", "3DS"],
        "Sega": ["Master System", "Mega Drive/Genesis", "Saturn", "Dreamcast"],
        "Xbox": ["Xbox", "Xbox 360", "Xbox One", "Xbox Series X/S"],
        "Other": ["Atari 2600", "Neo Geo", "PC Linux", "PC macOS"]
    }

    # ROADMAP TEXTS: Translations for roadmap popup
    ROADMAP_TEXTS = {
        "pt": {
            "header": "Plataformas em Desenvolvimento",
            "desc": "Estas plataformas serão adicionadas em futuras atualizações:",
            "note": "Nota: As atualizações são gratuitas para compradores do framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Outros"
            }
        },
        "en": {
            "header": "Platforms in Development",
            "desc": "These platforms will be added in future updates:",
            "note": "Note: Updates are free for framework purchasers.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Other"
            }
        },
        "es": {
            "header": "Plataformas en Desarrollo",
            "desc": "Estas plataformas se agregarán en futuras actualizaciones:",
            "note": "Nota: Las actualizaciones son gratuitas para los compradores del framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Otros"
            }
        },
        "fr": {
            "header": "Plateformes en Développement",
            "desc": "Ces plateformes seront ajoutées dans les futures mises à jour:",
            "note": "Note: Les mises à jour sont gratuites pour les acheteurs du framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Autres"
            }
        },
        "de": {
            "header": "Plattformen in Entwicklung",
            "desc": "Diese Plattformen werden in zukünftigen Updates hinzugefügt:",
            "note": "Hinweis: Updates sind kostenlos für Framework-Käufer.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Andere"
            }
        },
        "it": {
            "header": "Piattaforme in Sviluppo",
            "desc": "Queste piattaforme verranno aggiunte nei futuri aggiornamenti:",
            "note": "Nota: Gli aggiornamenti sono gratuiti per gli acquirenti del framework.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Altro"
            }
        },
        "ja": {
            "header": "開発中のプラットフォーム",
            "desc": "これらのプラットフォームは今後のアップデートで追加されます:",
            "note": "注: フレームワーク購入者はアップデートを無料で受け取れます。",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "任天堂クラシック",
                "Nintendo Portable": "任天堂ポータブル",
                "Sega": "セガ",
                "Xbox": "Xbox",
                "Other": "その他"
            }
        },
        "ko": {
            "header": "개발 중인 플랫폼",
            "desc": "이러한 플랫폼은 향후 업데이트에서 추가됩니다:",
            "note": "참고: 프레임워크 구매자는 무료로 업데이트를 받습니다.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "닌텐도 클래식",
                "Nintendo Portable": "닌텐도 휴대용",
                "Sega": "세가",
                "Xbox": "Xbox",
                "Other": "기타"
            }
        },
        "zh": {
            "header": "开发中的平台",
            "desc": "这些平台将在未来更新中添加:",
            "note": "注意: 框架购买者可免费获得更新。",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "任天堂经典",
                "Nintendo Portable": "任天堂掌机",
                "Sega": "世嘉",
                "Xbox": "Xbox",
                "Other": "其他"
            }
        },
        "ru": {
            "header": "Платформы в Разработке",
            "desc": "Эти платформы будут добавлены в будущих обновлениях:",
            "note": "Примечание: Обновления бесплатны для покупателей фреймворка.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Другое"
            }
        },
        "ar": {
            "header": "المنصات قيد التطوير",
            "desc": "ستتم إضافة هذه المنصات في التحديثات المستقبلية:",
            "note": "ملاحظة: التحديثات مجانية لمشتري الإطار.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "أخرى"
            }
        },
        "hi": {
            "header": "विकास में प्लेटफ़ॉर्म",
            "desc": "ये प्लेटफ़ॉर्म भविष्य के अपडेट में जोड़े जाएंगे:",
            "note": "नोट: फ्रेमवर्क खरीदारों के लिए अपडेट मुफ्त हैं।",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "अन्य"
            }
        },
        "tr": {
            "header": "Geliştirme Aşamasındaki Platformlar",
            "desc": "Bu platformlar gelecek güncellemelerde eklenecektir:",
            "note": "Not: Güncellemeler framework alıcıları için ücretsizdir.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Diğer"
            }
        },
        "pl": {
            "header": "Platformy w Rozwoju",
            "desc": "Te platformy zostaną dodane w przyszłych aktualizacjach:",
            "note": "Uwaga: Aktualizacje są bezpłatne dla nabywców frameworka.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Inne"
            }
        },
        "nl": {
            "header": "Platforms in Ontwikkeling",
            "desc": "Deze platforms worden toegevoegd in toekomstige updates:",
            "note": "Opmerking: Updates zijn gratis voor framework-kopers.",
            "cats": {
                "PlayStation": "PlayStation",
                "Nintendo Classic": "Nintendo Classic",
                "Nintendo Portable": "Nintendo Portable",
                "Sega": "Sega",
                "Xbox": "Xbox",
                "Other": "Andere"
            }
        }
    }

    FONT_FAMILIES = {
        "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
        "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
        "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
        "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
        "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
        "Arial": "Arial, sans-serif"
    }

    SOURCE_LANGUAGES = {
        "AUTO-DETECTAR": "auto",
        "Japonês (日本語)": "ja",
        "Inglês (English)": "en",
        "Espanhol (Español)": "es",
        "Russo (Русский)": "ru",
        "Chinês Simplificado (简体)": "zh-cn",
        "Chinês Tradicional (繁體)": "zh-tw",
        "Coreano (한국어)": "ko",
        "Francês (Français)": "fr",
        "Alemão (Deutsch)": "de",
        "Italiano (Italiano)": "it",
        "Árabe (العربية)": "ar",
        "Hindi (हिन्दी)": "hi",
        "Turco (Türkçe)": "tr",
        "Polonês (Polski)": "pl"
    }

    TARGET_LANGUAGES = {
        "Português (PT-BR)": "pt",
        "English (US)": "en",
        "Español (ES)": "es",
        "Français (FR)": "fr",
        "Deutsch (DE)": "de",
        "Italiano (IT)": "it",
        "日本語 (Japanese)": "ja",
        "한국어 (Korean)": "ko",
        "中文 (Chinese)": "zh",
        "Русский (Russian)": "ru"
    }

    THEMES = {
        "Preto (Black)": {"window": "#0d0d0d", "text": "#ffffff", "button": "#1a1a1a", "accent": "#4a9eff"},
        "Cinza (Gray)": {"window": "#2d2d2d", "text": "#ffffff", "button": "#3d3d3d", "accent": "#5c9eff"},
        "Branco (White)": {"window": "#f0f0f0", "text": "#000000", "button": "#e1e1e1", "accent": "#308cc6"}
    }

    TRANSLATIONS = {
        "pt": {
            "title": "Extração - Otimização - Tradução IA - Reinserção",
            "tab1": "🔍 1. Extração", "tab2": "🧠 2. Tradução", "tab3": "📥 3. Reinserção", "tab4": "⚙️ 4. Configurações", "tab5": "🎨 5. Laboratório Gráfico",
            "platform": "Plataforma:", "rom_file": "Arquivo ROM", "no_rom": "[WARN] Nenhuma ROM selecionada",
            "select_rom": "Selecionar ROM", "extract_texts": "📄 Extrair Textos", "optimize_data": "🧹 Otimizar Dados",
            "extraction_progress": "Progresso da Extração", "optimization_progress": "Progresso da Otimização",
            "waiting": "Aguardando início...", "language_config": "🌍 Configuração de Idiomas",
            "source_language": "📖 Idioma de Origem (ROM)", "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Tradução", "api_config": "Configuração de API", "api_key": "API Key:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usar cache de traduções",
            "translation_progress": "Progresso da Tradução", "translate_ai": "🤖 Traduzir com IA",
            "stop_translation": "🛑 Parar Tradução",
            "original_rom": "ROM Original", "translated_file": "Arquivo Traduzido", "select_file": "Selecionar Arquivo",
            "output_rom": "💾 ROM Traduzida (Saída)", "reinsertion_progress": "Progresso da Reinserção",
            "reinsert": "Reinserir Tradução", "theme": "🎨 Tema Visual", "ui_language": "🌐 Idioma da Interface",
            "font_family": "🔤 Fonte da Interface",
            "log": "Log de Operações", "restart": "Reiniciar", "exit": "Sair",
            "developer": "Desenvolvido por: Celso (Programador Solo)", "in_dev": "EM DESENVOLVIMENTO",
            "file_to_translate": "📄 Arquivo para Traduzir (Otimizado)", "no_file": "Nenhum arquivo selecionado",
            "help_support": "🆘 Ajuda e Suporte", "manual_guide": "📘 Guia de Uso Profissional:",
            "contact_support": "📧 Dúvidas? Entre em contato:",
            "btn_stop": "Parar Tradução", "btn_close": "Fechar",
            "roadmap_item": "Próximos Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas em desenvolvimento:",
            "theme_black": "Preto", "theme_gray": "Cinza", "theme_white": "Branco",

            "gfx_toolbar": "Controles de Visualização", "gfx_format": "Formato:", "gfx_zoom": "Zoom:",
            "gfx_palette": "Paleta:", "gfx_offset": "Endereço (Hex):", "gfx_tiles_per_row": "Largura:",
            "gfx_num_tiles": "Núm. Tiles:", "gfx_canvas": "Visualizador de Tiles",
            "gfx_load_rom": "📂 Carregue uma ROM na Aba 1 para visualizar aqui",
            "gfx_navigation_hint": "Dica: Use as setas do teclado para navegar. Scroll para Zoom.",
            "gfx_analysis": "Ferramentas de Análise", "gfx_editing": "Ferramentas de Edição",
            "gfx_btn_sniffer": "🔍 Detectar Fontes", "gfx_btn_entropy": "[STATS] Scanner de Compressão",
            "gfx_btn_export": "📥 Exportar PNG", "gfx_btn_import": "📤 Importar e Reinserir",
            "gfx_entropy_group": "Análise de Entropia de Shannon",
            "gfx_entropy_click": "Clique em 'Scanner de Entropia' para analisar...",
            "gfx_btn_prev": "◀ Página Anterior", "gfx_btn_next": "Próxima Página ▶",

            "manual_gfx_title": "🎨 Guia: Edição Gráfica Avançada",
            "manual_gfx_body": "FORMATOS DE TILES POR CONSOLE:\n\n"
                            "• SNES: 4bpp (16 cores por tile)\n"
                            "• Game Boy: 2bpp (4 cores por tile)\n"
                            "• Game Boy Color: 2bpp (4 cores)\n"
                            "• NES: 2bpp (4 cores)\n"
                            "• GBA: 4bpp ou 8bpp\n"
                            "• PS1: 4bpp ou 8bpp\n\n"
                            "WORKFLOW RECOMENDADO:\n\n"
                            "1. Exporte os tiles para PNG\n"
                            "2. Edite no Paint/Photoshop SEM mudar a paleta de cores\n"
                            "3. Importe de volta - o sistema reconverte automaticamente\n\n"
                            "IMPORTANTE: Não adicione cores novas! Use apenas as cores existentes no PNG exportado."
        },
        "en": {
            "title": "Extraction - Optimization - AI Translation - Reinsertion",
            "tab1": "🔍 1. Extraction", "tab2": "🧠 2. Translation", "tab3": "📥 3. Reinsertion", "tab4": "⚙️ 4. Settings", "tab5": "🎨 5. Graphics Lab",
            "platform": "Platform:", "rom_file": "ROM File", "no_rom": "[WARN] No ROM selected",
            "select_rom": "Select ROM", "extract_texts": "📄 Extract Texts", "optimize_data": "🧹 Optimize Data",
            "extraction_progress": "Extraction Progress", "optimization_progress": "Optimization Progress",
            "waiting": "Waiting...", "language_config": "🌍 Language Configuration",
            "source_language": "📖 Source Language (ROM)", "target_language": "🎯 Target Language",
            "translation_mode": "Translation Mode", "api_config": "API Configuration", "api_key": "API Key:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Use translation cache",
            "translation_progress": "Translation Progress", "translate_ai": "🤖 Translate with AI",
            "stop_translation": "🛑 Stop Translation",
            "original_rom": "Original ROM", "translated_file": "Translated File", "select_file": "Select File",
            "output_rom": "💾 Translated ROM (Output)", "reinsertion_progress": "Reinsertion Progress",
            "reinsert": "Reinsert Translation", "theme": "🎨 Visual Theme", "ui_language": "🌐 Interface Language",
            "font_family": "🔤 Font Family",
            "log": "Operations Log", "restart": "Restart", "exit": "Exit",
            "developer": "Developed by: Celso (Solo Programmer)", "in_dev": "IN DEVELOPMENT",
            "file_to_translate": "📄 File to Translate (Optimized)", "no_file": "No file selected",
            "help_support": "🆘 Help & Support", "manual_guide": "📘 Professional User Guide:",
            "contact_support": "📧 Questions? Contact us:",
            "btn_stop": "Stop Translation", "btn_close": "Close",
            "roadmap_item": "Upcoming Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in development:","roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Other",
            "theme_black": "Black", "theme_gray": "Gray", "theme_white": "White",

            "gfx_toolbar": "Visualization Controls", "gfx_format": "Format:", "gfx_zoom": "Zoom:",
            "gfx_palette": "Palette:", "gfx_offset": "Address (Hex):", "gfx_tiles_per_row": "Width:",
            "gfx_num_tiles": "Num. Tiles:", "gfx_canvas": "Tile Viewer",
            "gfx_load_rom": "📂 Load a ROM in Tab 1 to view here",
            "gfx_navigation_hint": "Tip: Use keyboard arrows to navigate. Scroll to Zoom.",
            "gfx_analysis": "Analysis Tools", "gfx_editing": "Editing Tools",
            "gfx_btn_sniffer": "🔍 Detect Fonts", "gfx_btn_entropy": "[STATS] Compression Scanner",
            "gfx_btn_export": "📥 Export PNG", "gfx_btn_import": "📤 Import and Reinsert",
            "gfx_entropy_group": "Shannon Entropy Analysis",
            "gfx_entropy_click": "Click 'Entropy Scanner' to analyze...",
            "gfx_btn_prev": "◀ Previous Page", "gfx_btn_next": "Next Page ▶",

            "manual_gfx_title": "🎨 Guide: Advanced Graphics Editing",
            "manual_gfx_body": "TILE FORMATS BY CONSOLE:\n\n"
                            "• SNES: 4bpp (16 colors per tile)\n"
                            "• Game Boy: 2bpp (4 colors per tile)\n"
                            "• Game Boy Color: 2bpp (4 colors)\n"
                            "• NES: 2bpp (4 colors)\n"
                            "• GBA: 4bpp or 8bpp\n"
                            "• PS1: 4bpp or 8bpp\n\n"
                            "RECOMMENDED WORKFLOW:\n\n"
                            "1. Export tiles to PNG\n"
                            "2. Edit in Paint/Photoshop WITHOUT changing color palette\n"
                            "3. Import back - system auto-converts to tile format\n\n"
                            "IMPORTANT: Don't add new colors! Use only existing colors from exported PNG."

        },
        "es": {
            "title": "Extracción - Optimización - Traducción IA - Reinserción",
            "tab1": "🔍 1. Extracción", "tab2": "🧠 2. Traducción", "tab3": "📥 3. Reinserción", "tab4": "⚙️ Configuración",
            "platform": "Plataforma:", "rom_file": "Archivo ROM", "no_rom": "[WARN] Ninguna ROM seleccionada",
            "select_rom": "Seleccionar ROM", "extract_texts": "📄 Extraer Textos", "optimize_data": "🧹 Optimizar Datos",
            "extraction_progress": "Progreso de Extracción", "optimization_progress": "Progreso de Optimización",
            "waiting": "Esperando inicio...", "language_config": "🌍 Configuración de Idiomas",
            "source_language": "📖 Idioma de Origen (ROM)", "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Traducción", "api_config": "Configuración de API", "api_key": "Clave API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usar caché de traducciones",
            "translation_progress": "Progreso de Traducción", "translate_ai": "🤖 Traducir con IA",
            "stop_translation": "🛑 Detener Traducción",
            "original_rom": "ROM Original", "translated_file": "Archivo Traducido", "select_file": "Seleccionar Archivo",
            "output_rom": "💾 ROM Traducida (Salida)", "reinsertion_progress": "Progreso de Reinserción",
            "reinsert": "Reinsertar Traducción", "theme": "🎨 Tema Visual", "ui_language": "🌐 Idioma de la Interfaz",
            "font_family": "🔤 Familia de Fuente",
            "log": "Registro de Operaciones", "restart": "Reiniciar", "exit": "Salir",
            "developer": "Desarrollado por: Celso (Programador Solo)", "in_dev": "EN DESARROLLO",
            "file_to_translate": "📄 Archivo para Traducir (Optimizado)", "no_file": "Ningún archivo seleccionado",
            "help_support": "🆘 Ayuda y Soporte", "manual_guide": "📘 Guía de Uso Profesional:",
            "contact_support": "📧 ¿Preguntas? Contáctenos:",
            "btn_stop": "Detener Traducción", "btn_close": "Cerrar",
            "roadmap_item": "Próximas Consolas (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas en desarrollo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Otro",
            "theme_black": "Negro", "theme_gray": "Gris", "theme_white": "Blanco"
        },
        "fr": {
            "title": "Extraction - Optimisation - Traduction IA - Réinsertion",
            "tab1": "🔍 1. Extraction", "tab2": "🧠 2. Traduction", "tab3": "📥 3. Réinsertion", "tab4": "⚙️ Paramètres",
            "platform": "Plateforme:", "rom_file": "Fichier ROM", "no_rom": "[WARN] Aucune ROM sélectionnée",
            "select_rom": "Sélectionner ROM", "extract_texts": "📄 Extraire Textes", "optimize_data": "🧹 Optimiser Données",
            "extraction_progress": "Progression de l'Extraction", "optimization_progress": "Progression de l'Optimisation",
            "waiting": "En attente...", "language_config": "🌍 Configuration des Langues",
            "source_language": "📖 Langue Source (ROM)", "target_language": "🎯 Langue Cible",
            "translation_mode": "Mode de Traduction", "api_config": "Configuration API", "api_key": "Clé API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Utiliser le cache de traduction",
            "translation_progress": "Progression de la Traduction", "translate_ai": "🤖 Traduire avec IA",
            "stop_translation": "🛑 Arrêter Traduction",
            "original_rom": "ROM Originale", "translated_file": "Fichier Traduit", "select_file": "Sélectionner Fichier",
            "output_rom": "💾 ROM Traduite (Sortie)", "reinsertion_progress": "Progression de Réinsertion",
            "reinsert": "Réinsérer Traduction", "theme": "🎨 Thème Visuel", "ui_language": "🌐 Langue de l'Interface",
            "font_family": "🔤 Famille de Police",
            "log": "Journal des Opérations", "restart": "Redémarrer", "exit": "Quitter",
            "developer": "Développé par: Celso (Programmeur Solo)", "in_dev": "EN DÉVELOPPEMENT",
            "file_to_translate": "📄 Fichier à Traduire (Optimisé)", "no_file": "Aucun fichier sélectionné",
            "help_support": "🆘 Aide et Support", "manual_guide": "📘 Guide d'Utilisation Professionnel:",
            "contact_support": "📧 Questions? Contactez-nous:",
            "btn_stop": "Arrêter la Traduction", "btn_close": "Fermer",
            "roadmap_item": "Consoles à Venir (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plateformes en développement:",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Autres",
            "theme_black": "Noir", "theme_gray": "Gris", "theme_white": "Blanc"
        },
        "de": {
            "title": "Extraktion - Optimierung - KI-Übersetzung - Wiedereinfügung",
            "tab1": "🔍 1. Extraktion", "tab2": "🧠 2. Übersetzung", "tab3": "📥 3. Wiedereinfügung", "tab4": "⚙️ Einstellungen",
            "platform": "Plattform:", "rom_file": "ROM-Datei", "no_rom": "[WARN] Keine ROM ausgewählt",
            "select_rom": "ROM auswählen", "extract_texts": "📄 Texte Extrahieren", "optimize_data": "🧹 Daten Optimieren",
            "extraction_progress": "Extraktionsfortschritt", "optimization_progress": "Optimierungsfortschritt",
            "waiting": "Warten...", "language_config": "🌍 Sprachkonfiguration",
            "source_language": "📖 Quellsprache (ROM)", "target_language": "🎯 Zielsprache",
            "translation_mode": "Übersetzungsmodus", "api_config": "API-Konfiguration", "api_key": "API-Schlüssel:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Übersetzungscache verwenden",
            "translation_progress": "Übersetzungsfortschritt", "translate_ai": "🤖 Mit KI Übersetzen",
            "stop_translation": "🛑 Übersetzung Stoppen",
            "original_rom": "Original-ROM", "translated_file": "Übersetzte Datei", "select_file": "Datei auswählen",
            "output_rom": "💾 Übersetzte ROM (Ausgabe)", "reinsertion_progress": "Wiedereinfügungsfortschritt",
            "reinsert": "Übersetzung Einfügen", "theme": "🎨 Visuelles Thema", "ui_language": "🌐 Oberflächensprache",
            "font_family": "🔤 Schriftfamilie",
            "log": "Operationsprotokoll", "restart": "Neustart", "exit": "Beenden",
            "developer": "Entwickelt von: Celso (Solo-Programmierer)", "in_dev": "IN ENTWICKLUNG",
            "file_to_translate": "📄 Zu übersetzende Datei (Optimiert)", "no_file": "Keine Datei ausgewählt",
            "help_support": "🆘 Hilfe und Support", "manual_guide": "📘 Professionelle Benutzeranleitung:",
            "contact_support": "📧 Fragen? Kontaktieren Sie uns:",
            "btn_stop": "Übersetzung Stoppen", "btn_close": "Schließen",
            "roadmap_item": "Kommende Konsolen (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Plattformen in Entwicklung:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Andet",
            "theme_black": "Schwarz", "theme_gray": "Grau", "theme_white": "Weiß"
        },
        "it": {
            "title": "Estrazione - Ottimizzazione - Traduzione IA - Reinserimento",
            "tab1": "🔍 1. Estrazione", "tab2": "🧠 2. Traduzione", "tab3": "📥 3. Reinserimento", "tab4": "⚙️ Impostazioni",
            "platform": "Piattaforma:", "rom_file": "File ROM", "no_rom": "[WARN] Nessuna ROM selezionata",
            "select_rom": "Seleziona ROM", "extract_texts": "📄 Estrai Testi", "optimize_data": "🧹 Ottimizza Dati",
            "extraction_progress": "Progresso Estrazione", "optimization_progress": "Progresso Ottimizzazione",
            "waiting": "In attesa...", "language_config": "🌍 Configurazione Lingue",
            "source_language": "📖 Lingua Sorgente (ROM)", "target_language": "🎯 Lingua Destinazione",
            "translation_mode": "Modalità Traduzione", "api_config": "Configurazione API", "api_key": "Chiave API:",
            "workers": "Workers:", "timeout": "Timeout (s):", "use_cache": "Usa cache traduzioni",
            "translation_progress": "Progresso Traduzione", "translate_ai": "🤖 Traduci con IA",
            "stop_translation": "🛑 Ferma Traduzione",
            "original_rom": "ROM Originale", "translated_file": "File Tradotto", "select_file": "Seleziona File",
            "output_rom": "💾 ROM Tradotta (Output)", "reinsertion_progress": "Progresso Reinserimento",
            "reinsert": "Reinserisci Traduzione", "theme": "🎨 Tema Visivo", "ui_language": "🌐 Lingua Interfaccia",
            "font_family": "🔤 Famiglia di Caratteri",
            "log": "Registro Operazioni", "restart": "Riavvia", "exit": "Esci",
            "developer": "Sviluppato da: Celso (Programmatore Solo)", "in_dev": "IN SVILUPPO",
            "file_to_translate": "📄 File da Tradurre (Ottimizzato)", "no_file": "Nessun file selezionato",
            "help_support": "🆘 Aiuto e Supporto", "manual_guide": "📘 Guida Utente Professionale:",
            "contact_support": "📧 Domande? Contattaci:",
            "btn_stop": "Ferma Traduzione", "btn_close": "Chiudi",
            "roadmap_item": "Prossime Console (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Piattaforme in sviluppo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Altro",
            "theme_black": "Nero", "theme_gray": "Grigio", "theme_white": "Bianco"
        },
        "ja": {
                "title": "抽出 - 最適化 - AI翻訳 - 再挿入",
                "tab1": "🔍 1. 抽出", "tab2": "🧠 2. 翻訳", "tab3": "📥 3. 再挿入", "tab4": "⚙️ 設定",
                "platform": "プラットフォーム:", "rom_file": "📂 ROMファイル", "no_rom": "[WARN] ROM未選択",
                "select_rom": "📂 ROM選択", "extract_texts": "📄 テキスト抽出", "optimize_data": "🧹 データ最適化",
                "extraction_progress": "抽出進行状況", "optimization_progress": "最適化進行状況",
                "waiting": "待機中...", "language_config": "🌍 言語設定",
                "source_language": "📖 ソース言語 (ROM)", "target_language": "🎯 ターゲット言語",
                "translation_mode": "翻訳モード", "api_config": "API設定", "api_key": "APIキー:",
                "workers": "ワーカー:", "timeout": "タイムアウト (秒):", "use_cache": "翻訳キャッシュを使用",
                "translation_progress": "翻訳進行状況", "translate_ai": "🤖 AIで翻訳",
                "stop_translation": "🛑 翻訳を停止",
                "original_rom": "📂 オリジナルROM", "translated_file": "📄 翻訳済みファイル", "select_file": "📄 ファイル選択",
                "output_rom": "💾 翻訳済みROM (出力)", "reinsertion_progress": "再挿入進行状況",
                "reinsert": "翻訳を再挿入", "theme": "🎨 ビジュアルテーマ", "ui_language": "🌐 インターフェース言語",
                "font_family": "🔤 フォントファミリー",
                "log": "操作ログ", "restart": "再起動", "exit": "終了",
                "developer": "開発者: Celso (ソロプログラマー)", "in_dev": "開発中",
                "file_to_translate": "📄 翻訳するファイル (最適化済み)", "no_file": "📄 ファイル未選択",
                "help_support": "🆘 ヘルプとサポート", "manual_guide": "📘 プロフェッショナルユーザーガイド:",
            "contact_support": "📧 ご質問？お問い合わせ:",
            "btn_stop": "翻訳を停止", "btn_close": "閉じる",
                "roadmap_item": "今後のコンソール (ロードマップ)...", "roadmap_title": "ロードマップ",
                "roadmap_desc": "開発中のプラットフォーム:",
                "roadmap_cat_playstation": "PlayStation",
                "roadmap_cat_nintendo_classic": "Nintendo Classic",
                "roadmap_cat_nintendo_portable": "Nintendo Portable",
                "roadmap_cat_sega": "Sega",
                "roadmap_cat_xbox": "Xbox",
                "roadmap_cat_other": "その他",
                "theme_black": "黒", "theme_gray": "灰色", "theme_white": "白"
            },
        "ko": {
            "title": "추출 - 최적화 - AI 번역 - 재삽입",
            "tab1": "🔍 1. 추출", "tab2": "🧠 2. 번역", "tab3": "📥 3. 재삽입", "tab4": "⚙️ 설정",
            "platform": "플랫폼:", "rom_file": "ROM 파일", "no_rom": "[WARN] ROM 선택 안 됨",
            "select_rom": "ROM 선택", "extract_texts": "📄 텍스트 추출", "optimize_data": "🧹 데이터 최적화",
            "extraction_progress": "추출 진행률", "optimization_progress": "최적화 진행률",
            "waiting": "대기 중...", "language_config": "🌍 언어 설정",
            "source_language": "📖 소스 언어 (ROM)", "target_language": "🎯 대상 언어",
            "translation_mode": "번역 모드", "api_config": "API 구성", "api_key": "API 키:",
            "workers": "작업자:", "timeout": "타임아웃 (초):", "use_cache": "번역 캐시 사용",
            "translation_progress": "번역 진행률", "translate_ai": "🤖 AI로 번역",
            "stop_translation": "🛑 번역 중지",
            "original_rom": "원본 ROM", "translated_file": "번역된 파일", "select_file": "파일 선택",
            "output_rom": "💾 번역된 ROM (출력)", "reinsertion_progress": "재삽입 진행률",
            "reinsert": "번역 재삽입", "theme": "🎨 비주얼 테마", "ui_language": "🌐 인터페이스 언어",
            "font_family": "🔤 글꼴 패밀리",
            "log": "작업 로그", "restart": "재시작", "exit": "종료",
            "developer": "개발자: Celso (솔로 프로그래머)", "in_dev": "개발 중",
            "file_to_translate": "📄 번역할 파일 (최적화됨)", "no_file": "파일 선택 안 됨",
            "help_support": "🆘 도움말 및 지원", "manual_guide": "📘 전문 사용자 가이드:",
            "contact_support": "📧 질문이 있으신가요? 문의하기:",
            "btn_stop": "번역 중지", "btn_close": "닫기",
            "roadmap_item": "향후 콘솔 (로드맵)...", "roadmap_title": "로드맵",
            "roadmap_desc": "개발 중인 플랫폼:",
            "roadmap_cat_playstation": "플레이스테이션",
            "roadmap_cat_nintendo_classic": "닌텐도 클래식",
            "roadmap_cat_nintendo_portable": "닌텐도 포터블",
            "roadmap_cat_sega": "세가",
            "roadmap_cat_xbox": "엑스박스",
            "roadmap_cat_other": "기타",
            "roadmap_cat_playstation": "peulleiseuteisyeon",
            "roadmap_cat_nintendo_classic": "nintendo keullaesig",
            "roadmap_cat_nintendo_portable": "nintendo poteobeul",
            "roadmap_cat_sega": "sega",
            "roadmap_cat_xbox": "egseubagseu",
            "roadmap_cat_other": "gita",
            "theme_black": "검정", "theme_gray": "회색", "theme_white": "흰색"

        },
        "zh": {
            "title": "提取 - 优化 - AI翻译 - 重新插入",
            "tab1": "🔍 1. 提取", "tab2": "🧠 2. 翻译", "tab3": "📥 3. 重新插入", "tab4": "⚙️ 设置",
            "platform": "平台:", "rom_file": "ROM文件", "no_rom": "[WARN] 未选择ROM",
            "select_rom": "选择ROM", "extract_texts": "📄 提取文本", "optimize_data": "🧹 优化数据",
            "extraction_progress": "提取进度", "optimization_progress": "优化进度",
            "waiting": "等待中...", "language_config": "🌍 语言配置",
            "source_language": "📖 源语言 (ROM)", "target_language": "🎯 目标语言",
            "translation_mode": "翻译模式", "api_config": "API配置", "api_key": "API密钥:",
            "workers": "工作线程:", "timeout": "超时 (秒):", "use_cache": "使用翻译缓存",
            "translation_progress": "翻译进度", "translate_ai": "🤖 使用AI翻译",
            "stop_translation": "🛑 停止翻译",
            "original_rom": "原始ROM", "translated_file": "翻译文件", "select_file": "选择文件",
            "output_rom": "💾 翻译ROM (输出)", "reinsertion_progress": "重新插入进度",
            "reinsert": "重新插入翻译", "theme": "🎨 视觉主题", "ui_language": "🌐 界面语言",
            "font_family": "🔤 字体系列",
            "log": "操作日志", "restart": "重启", "exit": "退出",
            "developer": "开发者: Celso (独立程序员)", "in_dev": "开发中",
            "file_to_translate": "📄 要翻译的文件 (已优化)", "no_file": "未选择文件",
            "help_support": "🆘 帮助和支持", "manual_guide": "📘 专业用户指南:",
            "contact_support": "📧 有疑问？联系我们:",
            "btn_stop": "停止翻译", "btn_close": "关闭",
            "roadmap_item": "即将推出的游戏机 (路线图)...", "roadmap_title": "路线图",
            "roadmap_desc": "开发中的平台:",
            "theme_black": "黑色", "theme_gray": "灰色", "theme_white": "白色"
        },
        "ru": {
            "title": "Извлечение - Оптимизация - ИИ Перевод - Реинсерция",
            "tab1": "🔍 1. Извлечение", "tab2": "🧠 2. Перевод", "tab3": "📥 3. Реинсерция", "tab4": "⚙️ Настройки",
            "platform": "Платформа:", "rom_file": "ROM Файл", "no_rom": "[WARN] ROM не выбран",
            "select_rom": "Выбрать ROM", "extract_texts": "📄 Извлечь Тексты", "optimize_data": "🧹 Оптимизировать Данные",
            "extraction_progress": "Прогресс Извлечения", "optimization_progress": "Прогресс Оптимизации",
            "waiting": "Ожидание...", "language_config": "🌍 Настройка Языков",
            "source_language": "📖 Исходный Язык (ROM)", "target_language": "🎯 Целевой Язык",
            "translation_mode": "Режим Перевода", "api_config": "Настройка API", "api_key": "API Ключ:",
            "workers": "Воркеры:", "timeout": "Таймаут (сек):", "use_cache": "Использовать кэш переводов",
            "translation_progress": "Прогресс Перевода", "translate_ai": "🤖 Перевести с ИИ",
            "stop_translation": "🛑 Остановить Перевод",
            "original_rom": "Оригинальный ROM", "translated_file": "Переведенный Файл", "select_file": "Выбрать Файл",
            "output_rom": "💾 Переведенный ROM (Вывод)", "reinsertion_progress": "Прогресс Реинсерции",
            "reinsert": "Реинсертировать Перевод", "theme": "🎨 Визуальная Тема", "ui_language": "🌐 Язык Интерфейса",
            "font_family": "🔤 Семейство Шрифтов",
            "log": "Журнал Операций", "restart": "Перезапустить", "exit": "Выход",
            "developer": "Разработчик: Celso (Соло Программист)", "in_dev": "В РАЗРАБОТКЕ",
            "file_to_translate": "📄 Файл для Перевода (Оптимизирован)", "no_file": "Файл не выбран",
            "help_support": "🆘 Помощь и Поддержка", "manual_guide": "📘 Профессиональное Руководство:",
            "contact_support": "📧 Вопросы? Свяжитесь с нами:",
            "btn_stop": "Остановить Перевод", "btn_close": "Закрыть",
            "roadmap_item": "Предстоящие Консоли (Дорожная карта)...", "roadmap_title": "Дорожная карта",
            "roadmap_desc": "Платформы в разработке:",
            "theme_black": "Чёрный", "theme_gray": "Серый", "theme_white": "Белый"
        },
        "ar": {
            "title": "استخراج - تحسين - ترجمة الذكاء الاصطناعي - إعادة إدراج",
            "tab1": "🔍 1. استخراج", "tab2": "🧠 2. ترجمة", "tab3": "📥 3. إعادة إدراج", "tab4": "⚙️ إعدادات",
            "platform": "منصة:", "rom_file": "ملف ROM", "no_rom": "لم يتم تحديد ROM",
            "select_rom": "اختر ROM", "extract_texts": "استخراج النصوص", "optimize_data": "🧹 تحسين البيانات",
            "extraction_progress": "تقدم الاستخراج", "optimization_progress": "تقدم التحسين",
            "waiting": "في الانتظار...", "language_config": "🌍 تكوين اللغة",
            "source_language": "📖 اللغة المصدر (ROM)", "target_language": "🎯 اللغة المستهدفة",
            "translation_mode": "وضع الترجمة", "api_config": "تكوين API", "api_key": "مفتاح API:",
            "workers": "العمال:", "timeout": "المهلة (ثانية):", "use_cache": "استخدام ذاكرة التخزين المؤقت للترجمة",
            "translation_progress": "تقدم الترجمة", "translate_ai": "🤖 ترجمة بالذكاء الاصطناعي",
            "original_rom": "ROM الأصلي", "translated_file": "الملف المترجم", "select_file": "اختر ملف",
            "output_rom": "💾 ROM المترجم (الإخراج)", "reinsertion_progress": "تقدم إعادة الإدراج",
            "reinsert": "إعادة إدراج الترجمة", "theme": "🎨 السمة البصرية", "ui_language": "🌐 لغة الواجهة",
            "font_family": "🔤 عائلة الخط",
            "log": "سجل العمليات", "restart": "إعادة التشغيل", "exit": "خروج",
            "developer": "تطوير: Celso (مبرمج منفرد)", "in_dev": "قيد التطوير",
            "file_to_translate": "📄 ملف للترجمة (محسّن)", "no_file": "لم يتم تحديد ملف",
            "help_support": "🆘 المساعدة والدعم", "manual_guide": "📘 دليل المستخدم المحترف:",
            "contact_support": "📧 أسئلة؟ اتصل بنا:",
            "btn_stop": "إيقاف الترجمة", "btn_close": "إغلاق",
            "roadmap_item": "وحدات التحكم القادمة (خارطة الطريق)...", "roadmap_title": "خارطة الطريق",
            "roadmap_desc": "المنصات قيد التطوير:",
            "theme_black": "أسود", "theme_gray": "رمادي", "theme_white": "أبيض"
        },
        "hi": {
            "title": "निष्कर्षण - अनुकूलन - एआई अनुवाद - पुनः सम्मिलन",
            "tab1": "🔍 1. निष्कर्षण", "tab2": "🧠 2. अनुवाद", "tab3": "📥 3. पुनः सम्मिलन", "tab4": "⚙️ सेटिंग्स",
            "platform": "मंच:", "rom_file": "ROM फ़ाइल", "no_rom": "कोई ROM चयनित नहीं",
            "select_rom": "ROM चुनें", "extract_texts": "पाठ निकालें", "optimize_data": "🧹 डेटा अनुकूलित करें",
            "extraction_progress": "निष्कर्षण प्रगति", "optimization_progress": "अनुकूलन प्रगति",
            "waiting": "प्रतीक्षा में...", "language_config": "🌍 भाषा कॉन्फ़िगरेशन",
            "source_language": "📖 स्रोत भाषा (ROM)", "target_language": "🎯 लक्ष्य भाषा",
            "translation_mode": "अनुवाद मोड", "api_config": "API कॉन्फ़िगरेशन", "api_key": "API कुंजी:",
            "workers": "वर्कर्स:", "timeout": "टाइमआउट (सेकंड):", "use_cache": "अनुवाद कैश का उपयोग करें",
            "translation_progress": "अनुवाद प्रगति", "translate_ai": "🤖 एआई से अनुवाद करें",
            "original_rom": "मूल ROM", "translated_file": "अनुवादित फ़ाइल", "select_file": "फ़ाइल चुनें",
            "output_rom": "💾 अनुवादित ROM (आउटपुट)", "reinsertion_progress": "पुनः सम्मिलन प्रगति",
            "reinsert": "अनुवाद पुनः सम्मिलित करें", "theme": "🎨 दृश्य थीम", "ui_language": "🌐 इंटरफ़ेस भाषा",
            "font_family": "🔤 फ़ॉन्ट परिवार",
            "log": "ऑपरेशन लॉग", "restart": "पुनः आरंभ करें", "exit": "बाहर निकलें",
            "developer": "विकसित: Celso (एकल प्रोग्रामर)", "in_dev": "विकास में",
            "file_to_translate": "📄 अनुवाद करने के लिए फ़ाइल (अनुकूलित)", "no_file": "कोई फ़ाइल चयनित नहीं",
            "help_support": "🆘 सहायता और समर्थन", "manual_guide": "📘 पेशेवर उपयोगकर्ता गाइड:",
            "contact_support": "📧 सवाल? हमसे संपर्क करें:",
            "btn_stop": "अनुवाद रोकें", "btn_close": "बंद करें",
            "roadmap_item": "आगामी कंसोल (रोडमैप)...", "roadmap_title": "रोडमैप",
            "roadmap_desc": "विकास में प्लेटफ़ॉर्म:",
            "theme_black": "काला", "theme_gray": "स्लेटी", "theme_white": "सफेद"
        },
        "tr": {
            "title": "Çıkarma - Optimizasyon - Yapay Zeka Çevirisi - Yeniden Ekleme",
            "tab1": "🔍 1. Çıkarma", "tab2": "🧠 2. Çeviri", "tab3": "📥 3. Yeniden Ekleme", "tab4": "⚙️ Ayarlar",
            "platform": "Platform:", "rom_file": "ROM Dosyası", "no_rom": "ROM seçilmedi",
            "select_rom": "ROM Seç", "extract_texts": "METİNLERİ ÇIKAR", "optimize_data": "🧹 VERİLERİ OPTİMİZE ET",
            "extraction_progress": "Çıkarma İlerlemesi", "optimization_progress": "Optimizasyon İlerlemesi",
            "waiting": "Bekleniyor...", "language_config": "🌍 Dil Yapılandırması",
            "source_language": "📖 Kaynak Dil (ROM)", "target_language": "🎯 Hedef Dil",
            "translation_mode": "Çeviri Modu", "api_config": "API Yapılandırması", "api_key": "API Anahtarı:",
            "workers": "İşçiler:", "timeout": "Zaman Aşımı (sn):", "use_cache": "Çeviri önbelleğini kullan",
            "translation_progress": "Çeviri İlerlemesi", "translate_ai": "🤖 YAPAY ZEKA İLE ÇEVİR",
            "original_rom": "Orijinal ROM", "translated_file": "Çevrilmiş Dosya", "select_file": "Dosya Seç",
            "output_rom": "💾 Çevrilmiş ROM (Çıktı)", "reinsertion_progress": "Yeniden Ekleme İlerlemesi",
            "reinsert": "ÇEVİRİYİ YENİDEN EKLE", "theme": "🎨 Görsel Tema", "ui_language": "🌐 Arayüz Dili",
            "font_family": "🔤 Yazı Tipi Ailesi",
            "log": "İşlem Günlüğü", "restart": "YENİDEN BAŞLAT", "exit": "ÇIKIŞ",
            "developer": "Geliştirici: Celso (Solo Programcı)", "in_dev": "GELİŞTİRMEDE",
            "file_to_translate": "📄 Çevrilecek Dosya (Optimize Edilmiş)", "no_file": "Dosya seçilmedi",
            "help_support": "🆘 Yardım ve Destek", "manual_guide": "📘 Profesyonel Kullanıcı Kılavuzu:",
            "contact_support": "📧 Sorularınız mı var? Bize ulaşın:",
            "btn_stop": "ÇEVİRİYİ DURDUR", "btn_close": "KAPAT",
            "roadmap_item": "Yaklaşan Konsollar (Yol Haritası)...", "roadmap_title": "Yol Haritası",
            "roadmap_desc": "Geliştirme aşamasındaki platformlar:",
            "theme_black": "Siyah", "theme_gray": "Gri", "theme_white": "Beyaz"
        },
        "pl": {
            "title": "Ekstrakcja - Optymalizacja - Tłumaczenie AI - Reinsercja",
            "tab1": "🔍 1. Ekstrakcja", "tab2": "🧠 2. Tłumaczenie", "tab3": "📥 3. Reinsercja", "tab4": "⚙️ Ustawienia",
            "platform": "Platforma:", "rom_file": "Plik ROM", "no_rom": "Nie wybrano ROM",
            "select_rom": "Wybierz ROM", "extract_texts": "WYODRĘBNIJ TEKSTY", "optimize_data": "🧹 OPTYMALIZUJ DANE",
            "extraction_progress": "Postęp Ekstrakcji", "optimization_progress": "Postęp Optymalizacji",
            "waiting": "Oczekiwanie...", "language_config": "🌍 Konfiguracja Języka",
            "source_language": "📖 Język Źródłowy (ROM)", "target_language": "🎯 Język Docelowy",
            "translation_mode": "Tryb Tłumaczenia", "api_config": "Konfiguracja API", "api_key": "Klucz API:",
            "workers": "Pracownicy:", "timeout": "Limit czasu (s):", "use_cache": "Użyj pamięci podręcznej tłumaczeń",
            "translation_progress": "Postęp Tłumaczenia", "translate_ai": "🤖 TŁUMACZ Z AI",
            "original_rom": "Oryginalny ROM", "translated_file": "Przetłumaczony Plik", "select_file": "Wybierz Plik",
            "output_rom": "💾 Przetłumaczony ROM (Wyjście)", "reinsertion_progress": "Postęp Reinsercji",
            "reinsert": "WSTAW TŁUMACZENIE", "theme": "🎨 Motyw Wizualny", "ui_language": "🌐 Język Interfejsu",
            "font_family": "🔤 Rodzina Czcionek",
            "log": "Dziennik Operacji", "restart": "RESTART", "exit": "WYJŚCIE",
            "developer": "Opracowane przez: Celso (Programista Solo)", "in_dev": "W ROZWOJU",
            "file_to_translate": "📄 Plik do Tłumaczenia (Zoptymalizowany)", "no_file": "Nie wybrano pliku",
            "help_support": "🆘 Pomoc i Wsparcie", "manual_guide": "📘 Profesjonalny Przewodnik:",
            "contact_support": "📧 Pytania? Skontaktuj się z nami:",
            "btn_stop": "ZATRZYMAJ TŁUMACZENIE", "btn_close": "ZAMKNIJ",
            "roadmap_item": "Nadchodzące Konsole (Mapa drogowa)...", "roadmap_title": "Mapa drogowa",
            "roadmap_desc": "Platformy w rozwoju:",
            "theme_black": "Czarny", "theme_gray": "Szary", "theme_white": "Biały"
        },
        "nl": {
            "title": "Extractie - Optimalisatie - AI Vertaling - Herinvoer",
            "tab1": "🔍 1. Extractie", "tab2": "🧠 2. Vertaling", "tab3": "📥 3. Herinvoer", "tab4": "⚙️ Instellingen",
            "platform": "Platform:", "rom_file": "ROM Bestand", "no_rom": "Geen ROM geselecteerd",
            "select_rom": "Selecteer ROM", "extract_texts": "TEKSTEN EXTRAHEREN", "optimize_data": "🧹 DATA OPTIMALISEREN",
            "extraction_progress": "Extractie Voortgang", "optimization_progress": "Optimalisatie Voortgang",
            "waiting": "Wachten...", "language_config": "🌍 Taalconfiguratie",
            "source_language": "📖 Brontaal (ROM)", "target_language": "🎯 Doeltaal",
            "translation_mode": "Vertaalmodus", "api_config": "API Configuratie", "api_key": "API Sleutel:",
            "workers": "Workers:", "timeout": "Time-out (s):", "use_cache": "Gebruik vertaalcache",
            "translation_progress": "Vertaalvoortgang", "translate_ai": "🤖 VERTALEN MET AI",
            "original_rom": "Originele ROM", "translated_file": "Vertaald Bestand", "select_file": "Selecteer Bestand",
            "output_rom": "💾 Vertaalde ROM (Uitvoer)", "reinsertion_progress": "Herinvoer Voortgang",
            "reinsert": "VERTALING HERINVOEREN", "theme": "🎨 Visueel Thema", "ui_language": "🌐 Interface Taal",
            "font_family": "🔤 Lettertypefamilie",
            "log": "Operatielogboek", "restart": "HERSTARTEN", "exit": "AFSLUITEN",
            "developer": "Ontwikkeld door: Celso (Solo Programmeur)", "in_dev": "IN ONTWIKKELING",
            "file_to_translate": "📄 Te vertalen bestand (Geoptimaliseerd)", "no_file": "Geen bestand geselecteerd",
            "help_support": "🆘 Hulp en Ondersteuning", "manual_guide": "📘 Professionele Gebruikersgids:",
            "contact_support": "📧 Vragen? Neem contact op:",
            "btn_stop": "VERTALING STOPPEN", "btn_close": "SLUITEN",
            "roadmap_item": "Komende Consoles (Roadmap)...", "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in ontwikkeling:",
            "theme_black": "Zwart", "theme_gray": "Grijs", "theme_white": "Wit"
        }
    }
@classmethod
def ensure_directories(cls):
        cls.ROMS_DIR.mkdir(exist_ok=True, parents=True)
        cls.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


class ThemeManager:
    @staticmethod
    def apply(app: QApplication, theme_name: str):
        if theme_name not in ProjectConfig.THEMES:
            theme_name = "Preto (Black)"
        theme = ProjectConfig.THEMES[theme_name]
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["window"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["button"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["button"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff0000"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        app.setPalette(palette)


def _obfuscate_key(key: str) -> str:
    """Ofusca a API key usando base64 (não é criptografia real)."""
    if not key:
        return ""
    return base64.b64encode(key.encode()).decode()


def _deobfuscate_key(obfuscated: str) -> str:
    """Decodifica a API key ofuscada."""
    if not obfuscated:
        return ""
    try:
        return base64.b64decode(obfuscated.encode()).decode()
    except:
        return ""


# ================================================================================
# RTCE Process Selection Dialog
# ================================================================================
class RTCEProcessDialog(QDialog):
    """Diálogo para selecionar processo do emulador e configurar captura."""

    def __init__(self, platform: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.setWindowTitle("Captura Runtime - Configuração")
        self.setMinimumSize(1400, 900)
        self.selected_process = None
        self.duration = 300
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info_label = QLabel(f"[INFO] <b>Runtime Text Capture Engine</b><br>"
                          f"Plataforma: {self.platform}<br><br>"
                          f"<i>Selecione o processo do emulador em execução:</i>")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #2d2d2d; border-radius: 6px;")
        layout.addWidget(info_label)

        # Lista de processos
        process_group = QGroupBox("Processos em Execução")
        process_layout = QVBoxLayout()

        # Detectar processos
        self.process_list = QComboBox()
        self.process_list.setMinimumHeight(35)

        # Processos comuns por plataforma
        emulators_map = {
            'SNES': ['snes9x-x64.exe', 'snes9x.exe', 'bsnes.exe', 'higan.exe', 'zsnes.exe'],
            'NES': ['fceux.exe', 'nestopia.exe', 'mesen.exe'],
            'N64': ['project64.exe', 'mupen64plus.exe', 'm64p.exe'],
            'GBA': ['visualboyadvance.exe', 'mgba.exe', 'vba-m.exe'],
            'NDS': ['desmume.exe', 'melonds.exe', 'no$gba.exe'],
            'GENESIS': ['kega-fusion.exe', 'gens.exe', 'blastem.exe'],
            'PS1': ['epsxe.exe', 'pcsxr.exe', 'duckstation.exe', 'mednafen.exe'],
            'PS2': ['pcsx2.exe', 'pcsx2-qt.exe'],
            'PC_WINDOWS': ['*.exe']
        }

        expected_emulators = emulators_map.get(self.platform, [])

        # Listar processos rodando
        try:
            import psutil
            running_processes = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    # Filtrar apenas emuladores esperados
                    if any(emu.lower().replace('*', '') in proc_name for emu in expected_emulators):
                        running_processes.append((proc.info['name'], proc.info['pid']))
                except:
                    continue

            if running_processes:
                for proc_name, pid in running_processes:
                    self.process_list.addItem(f"{proc_name} (PID: {pid})", proc_name)
            else:
                self.process_list.addItem("Nenhum emulador detectado", None)
        except ImportError:
            self.process_list.addItem("psutil não instalado - Digite manualmente", None)

        # Opção manual
        self.process_list.addItem("📝 Digite o nome manualmente...", "manual")

        process_layout.addWidget(self.process_list)

        # Campo manual
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Ex: snes9x-x64.exe")
        self.manual_input.setVisible(False)
        self.manual_input.setMinimumHeight(30)
        process_layout.addWidget(self.manual_input)

        self.process_list.currentIndexChanged.connect(self.on_process_changed)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # Configurações
        config_group = QGroupBox("Configurações de Captura")
        config_layout = QFormLayout()

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(30, 3600)
        self.duration_spin.setValue(300)
        self.duration_spin.setSuffix(" segundos")
        self.duration_spin.setMinimumHeight(30)
        config_layout.addRow("Duração:", self.duration_spin)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Dicas
        tips_label = QLabel("💡 <b>Dicas:</b><br>"
                          "• Abra o emulador e carregue o jogo ANTES<br>"
                          "• Durante a captura, navegue pelos menus<br>"
                          "• Abra diálogos e troque de telas<br>"
                          "• Quanto mais você jogar, mais texto será capturado")
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet("padding: 10px; background-color: #1a3a1a; border-radius: 6px; color: #aaffaa;")
        layout.addWidget(tips_label)

        # Botões
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.clicked.connect(self.reject)

        start_btn = QPushButton("▶️ Iniciar Captura")
        start_btn.setMinimumHeight(35)
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        start_btn.clicked.connect(self.accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(start_btn)
        layout.addLayout(button_layout)

    def on_process_changed(self, index):
        """Mostra campo manual se selecionado."""
        data = self.process_list.currentData()
        self.manual_input.setVisible(data == "manual")

    def get_selected_process(self) -> str:
        """Retorna nome do processo selecionado."""
        data = self.process_list.currentData()
        if data == "manual":
            return self.manual_input.text().strip()
        elif data:
            return data
        else:
            # Pegar do texto do item (formato: "nome.exe (PID: 1234)")
            text = self.process_list.currentText()
            if "(PID:" in text:
                return text.split("(PID:")[0].strip()
            return ""

    def get_duration(self) -> int:
        """Retorna duração em segundos."""
        return self.duration_spin.value()

    # --- COLE AQUI (FORA DA MAINWINDOW) ---
class RTCEWorker(QThread):
    """Motor v 6.0: Captura texto da RAM em tempo real sem travar a interface."""
    log_signal = pyqtSignal(str)
    text_found_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, platform_name, parent=None):
        # CORREÇÃO: Isso evita o erro de "unexpected type 'str'"
        super().__init__(parent)
        self.platform_name = platform_name
        self._is_running = True
        self._all_texts = []

    def run(self):
        try:
            import time
            from rtce_core.rtce_engine import RTCEEngine

            # Inicializa o motor v 6.0
            engine = RTCEEngine(platform=self.platform_name)

            if not engine.attach_to_process():
                self.log_signal.emit("[ERROR] [RTCE] Emulador não detectado. Abra o jogo primeiro!")
                return

            self.log_signal.emit(f"[OK] [RTCE] Conectado ao processo! Capturando {self.platform_name}...")

            while self._is_running:
                results = engine.scan_once(deduplicate=True)
                if results:
                    for r in results:
                        # Filtro de Perfeccionista: Mostra endereço e texto
                        msg = f"[0x{r.offset}] {r.text}"
                        self.text_found_signal.emit(msg)
                        self._all_texts.append(r.text)

                self.msleep(1000) # Verifica a cada 1 segundo

            engine.detach_from_process()
            self.finished_signal.emit(self._all_texts)

        except Exception as e:
            self.log_signal.emit(f"[ERROR] Erro no Motor RTCE: {_sanitize_error(e)}")
            self.error_signal.emit(_sanitize_error(e))

    def stop(self):
        self._is_running = False

class MainWindow(QMainWindow):
    # --- 1. FUNÇÃO LOG (ALINHADA COM 4 ESPAÇOS) ---
    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.append(f"[{timestamp}] {message}")
            from PyQt6.QtGui import QTextCursor
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        else:
            print(f"[{timestamp}] {message}")

    def clear_translation_cache(self):
        """Limpa o cache de traduções para forçar retradução."""
        from pathlib import Path

        # Cache fica na pasta do framework
        framework_dir = Path(__file__).parent.parent

        # Arquivos de cache possíveis
        cache_names = [
            "cache_traducoes.json",
            "translation_cache.json",
            "cache_translations.json"
        ]

        cache_files = []
        for name in cache_names:
            cache_path = framework_dir / name
            if cache_path.exists():
                cache_files.append(cache_path)

        # Também procura na pasta atual de trabalho
        cwd = Path.cwd()
        for name in cache_names:
            cache_path = cwd / name
            if cache_path.exists() and cache_path not in cache_files:
                cache_files.append(cache_path)

        if not cache_files:
            QMessageBox.information(self, "Cache", "Nenhum cache encontrado.")
            return

        # Mostra arquivos encontrados
        files_info = "\n".join([f"• {f.name} ({f.stat().st_size // 1024} KB)" for f in cache_files])

        reply = QMessageBox.question(
            self,
            "Limpar Cache",
            f"Encontrado(s) {len(cache_files)} arquivo(s) de cache:\n\n{files_info}\n\nRemover para forçar retradução?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                for f in cache_files:
                    f.unlink()
                self.log(f"🗑️ Cache limpo: {len(cache_files)} arquivo(s) removido(s)")
                QMessageBox.information(self, "Cache", f"Cache limpo!\n{len(cache_files)} arquivo(s) removido(s).")
            except Exception as e:
                self.log(f"[ERROR] Erro ao limpar cache: {_sanitize_error(e)}")
                QMessageBox.warning(self, "Erro", f"Erro ao limpar cache:\n{_sanitize_error(e)}")

    # --- 2. INICIALIZAÇÃO CORRIGIDA ---
    def __init__(self):
        super().__init__()

        # Variáveis de Estado
        self.original_rom_path = None
        self.extracted_file = None
        self.optimized_file = None
        self.translated_file = None
        self.detected_platform_code = None  # ADICIONE ESTA LINHA

        # RTCE State (Motor v 6.0)
        self.rtce_thread = None

        self.current_theme = "Preto (Black)"
        self.current_ui_lang = "pt"  # Português do Brasil como padrão
        self.current_font_family = "Padrão (Segoe UI + CJK Fallback)"

        # Settings
        self.source_language_code = "auto"
        self.target_language_code = "pt"

        # Workers
        self.extract_thread = None
        self.optimize_thread = None
        self.translate_thread = None
        self.reinsert_thread = None
        self.engine_detection_thread = None
        self._advanced_jsonl_confirmed_path = ""
        self._realtime_filter_technical_noise = False

        # [OK] CONFIGURAÇÕES DO OTIMIZADOR (Expert Mode)
        self.optimizer_config = {
            'preserve_commands': True,
            'replace_symbol': '@',
            'replace_with': ' ',
            'remove_overlaps': True
        }

        self.init_ui()
    def setup_menu(self):
        """Cria o Menu Superior (Limpa tudo antes para garantir que Ajuda suma)."""
        menu_bar = self.menuBar()
        menu_bar.clear()  # <--- ESSA LINHA GARANTE QUE O MENU "AJUDA" SUMA

        # Estilo Profissional (Cinza, sem verde no topo)
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 10pt;
                border-bottom: 1px solid #1a1a1a;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 10px;
                margin-top: 1px;
            }
            QMenuBar::item:selected {
                background-color: #3d3d3d;
                color: #ffffff;
                border-radius: 4px;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
                color: white;
                border-radius: 2px;
            }
        """)

        # --- MENU ARQUIVO ---
        file_menu = menu_bar.addMenu("Arquivo")

        # Ação Reiniciar
        action_restart = file_menu.addAction("🔄 Reiniciar Sistema")
        action_restart.setShortcut("Ctrl+R")
        action_restart.triggered.connect(self.restart_application)

        file_menu.addSeparator()

        # Ação Sair
        action_exit = file_menu.addAction("🚪 Sair")
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)

        # Menu Configurações removido - opções eram inúteis

    def show_optimizer_settings_dialog(self):
        """Abre o diálogo de configurações avançadas do otimizador."""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ Configurações Avançadas do Otimizador")
        dialog.setMinimumSize(550, 400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # ========== AVISO NO TOPO ==========
        warning_label = QLabel("[WARN] MODO ESPECIALISTA: Estas configurações afetam a limpeza dos textos.\nRecomendado apenas para Romhackers.")
        warning_label.setStyleSheet("""
            QLabel {
                background-color: #FF9800;
                color: #000000;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # ========== SEÇÃO: FILTROS ==========
        filters_group = QGroupBox("🔍 Filtros de Validação")
        filters_layout = QVBoxLayout()

        # Checkbox: Preservar comandos
        self.preserve_commands_cb = QCheckBox("Preservar comandos de sistema (\\s, [hex], {code})")
        self.preserve_commands_cb.setChecked(self.optimizer_config['preserve_commands'])
        self.preserve_commands_cb.setStyleSheet("QCheckBox { font-size: 9pt; }")
        filters_layout.addWidget(self.preserve_commands_cb)

        # Checkbox: Remover overlaps
        self.remove_overlaps_cb = QCheckBox("Remover Overlaps (Ecos de texto - Mushroom/ushroom/shroom)")
        self.remove_overlaps_cb.setChecked(self.optimizer_config['remove_overlaps'])
        self.remove_overlaps_cb.setStyleSheet("QCheckBox { font-size: 9pt; }")
        filters_layout.addWidget(self.remove_overlaps_cb)

        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # ========== SEÇÃO: SUBSTITUIÇÃO DE SÍMBOLOS ==========
        replace_group = QGroupBox("🔄 Substituição de Símbolos")
        replace_layout = QHBoxLayout()

        # Label: "Trocar símbolo:"
        replace_label1 = QLabel("Trocar símbolo:")
        replace_layout.addWidget(replace_label1)

        # Input: Caractere original
        self.replace_symbol_input = QLineEdit(self.optimizer_config['replace_symbol'])
        self.replace_symbol_input.setMaxLength(1)
        self.replace_symbol_input.setFixedWidth(50)
        self.replace_symbol_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_symbol_input.setStyleSheet("QLineEdit { font-size: 12pt; font-weight: bold; }")
        replace_layout.addWidget(self.replace_symbol_input)

        # Label: "por:"
        replace_label2 = QLabel("por:")
        replace_layout.addWidget(replace_label2)

        # Input: Novo caractere
        self.replace_with_input = QLineEdit(self.optimizer_config['replace_with'])
        self.replace_with_input.setMaxLength(1)
        self.replace_with_input.setFixedWidth(50)
        self.replace_with_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_with_input.setStyleSheet("QLineEdit { font-size: 12pt; font-weight: bold; }")
        replace_layout.addWidget(self.replace_with_input)

        replace_layout.addStretch()

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)

        # ========== INFORMAÇÃO ADICIONAL ==========
        info_label = QLabel("💡 Dica: A substituição de símbolos é útil para converter caracteres especiais\nusados como espaços em ROMs antigas (@, _, etc.) por espaços reais.")
        info_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 8pt;
                padding: 5px;
            }
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # ========== BOTÕES ==========
        buttons_layout = QHBoxLayout()

        save_btn = QPushButton("[OK] Salvar")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(lambda: self.save_optimizer_config(dialog))

        cancel_btn = QPushButton("[ERROR] Cancelar")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        dialog.exec()

    def save_optimizer_config(self, dialog):
        """Salva as configurações do otimizador e fecha o diálogo."""
        # Atualiza as configurações
        self.optimizer_config['preserve_commands'] = self.preserve_commands_cb.isChecked()
        self.optimizer_config['remove_overlaps'] = self.remove_overlaps_cb.isChecked()
        self.optimizer_config['replace_symbol'] = self.replace_symbol_input.text() or '@'
        self.optimizer_config['replace_with'] = self.replace_with_input.text() or ' '

        # Log das mudanças
        self.log("⚙️ Configurações do Otimizador atualizadas:")
        self.log(f"   • Preservar comandos: {self.optimizer_config['preserve_commands']}")
        self.log(f"   • Remover overlaps: {self.optimizer_config['remove_overlaps']}")
        self.log(f"   • Substituir '{self.optimizer_config['replace_symbol']}' por '{self.optimizer_config['replace_with']}'")

        QMessageBox.information(
            self,
            "[OK] Configurações Salvas",
            "As configurações do otimizador foram atualizadas com sucesso!\n\nElas serão aplicadas na próxima otimização."
        )

        dialog.accept()

    def tr(self, key: str) -> str:
        """
        i18n translation with triple fallback:
        1. Current UI language (self.current_ui_lang)
        2. English (en) - universal fallback
        3. [KEY_NAME] - debug mode (makes missing keys visible)
        """
        # Level 1: Current language
        current_translations = ProjectConfig.load_translations(self.current_ui_lang)
        translation = current_translations.get(key)

        # Level 2: Fallback to English
        if translation is None:
            en_translations = ProjectConfig.load_translations("en")
            translation = en_translations.get(key)

        # Level 3: Visual debug fallback
        if translation is None:
            return key.capitalize()

        return translation

    def get_translated_theme_name(self, internal_key: str) -> str:
        """Convert internal theme key to translated theme name."""
        translation_key = ProjectConfig.THEME_TRANSLATION_KEYS.get(internal_key)
        if translation_key:
            return self.tr(translation_key)
        return internal_key  # Fallback to internal key if not found

    def get_internal_theme_key(self, translated_name: str) -> str:
        """Convert translated theme name back to internal theme key."""
        # Check all internal keys to find which one translates to this name
        for internal_key, translation_key in ProjectConfig.THEME_TRANSLATION_KEYS.items():
            if self.tr(translation_key) == translated_name:
                return internal_key
        return translated_name  # Fallback if not found

    def get_all_translated_theme_names(self) -> list:
        """Get all theme names in translated form, maintaining order."""
        translated_names = []
        for internal_key in ProjectConfig.THEMES.keys():
            translated_names.append(self.get_translated_theme_name(internal_key))
        return translated_names

    def get_translated_source_language_name(self, internal_key: str) -> str:
        """Convert internal source language key to translated name."""
        if internal_key == "AUTO-DETECTAR":
            return self.tr("auto_detect")
        return internal_key  # Return as-is for other languages (they have native names)

    def get_internal_source_language_key(self, translated_name: str) -> str:
        """Convert translated source language name back to internal key."""
        if translated_name == self.tr("auto_detect"):
            return "AUTO-DETECTAR"
        return translated_name  # Return as-is for other languages

    def get_all_translated_source_languages(self) -> list:
        """Get all source language names with AUTO-DETECTAR translated."""
        translated_names = []
        for internal_key in ProjectConfig.SOURCE_LANGUAGES.keys():
            translated_names.append(self.get_translated_source_language_name(internal_key))
        return translated_names

    def check_eula_and_license(self):
        """COMMERCIAL: Check EULA acceptance and license activation."""
        if SecurityManager is None:
            return

        # Check EULA
        if not SecurityManager.is_eula_accepted():
            eula_dialog = QDialog(self)
            eula_dialog.setWindowTitle("NeuroROM AI - EULA & Disclaimer")
            eula_dialog.setMinimumSize(700, 600)
            eula_dialog.setModal(True)

            layout = QVBoxLayout(eula_dialog)

            # EULA Text
            eula_text = QTextEdit()
            eula_text.setReadOnly(True)
            eula_text.setPlainText(SecurityManager.EULA_TEXT)
            layout.addWidget(eula_text)

            # Buttons
            button_layout = QHBoxLayout()
            accept_btn = QPushButton("Accept")
            accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reject_btn = QPushButton("Reject")
            reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def on_accept():
                SecurityManager.accept_eula()
                eula_dialog.accept()

            def on_reject():
                QMessageBox.critical(
                    eula_dialog,
                    "EULA Required",
                    "You must accept the EULA to use NeuroROM AI."
                )
                sys.exit(0)

            accept_btn.clicked.connect(on_accept)
            reject_btn.clicked.connect(on_reject)

            button_layout.addWidget(reject_btn)
            button_layout.addWidget(accept_btn)
            layout.addLayout(button_layout)

            eula_dialog.exec()

        # Check License
        if not SecurityManager.is_licensed():
            license_dialog = QDialog(self)
            license_dialog.setWindowTitle("NeuroROM AI - License Activation")
            license_dialog.setMinimumSize(500, 300)
            license_dialog.setModal(True)

            layout = QVBoxLayout(license_dialog)

            info_label = QLabel(
                "<h2>License Activation Required</h2>"
                "<p>Enter your Gumroad license key to activate NeuroROM AI.</p>"
                "<p><b>For development:</b> Use <code>DEV-LICENSE</code></p>"
            )
            info_label.setWordWrap(True)
            info_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(info_label)

            key_label = QLabel("License Key:")
            layout.addWidget(key_label)

            key_input = QLineEdit()
            key_input.setPlaceholderText("NEUROROM-GUMROAD-XXXXXXXXXXXX")
            layout.addWidget(key_input)

            status_label = QLabel("")
            status_label.setStyleSheet("color: red;")
            layout.addWidget(status_label)

            button_layout = QHBoxLayout()
            activate_btn = QPushButton("Activate")
            activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            skip_btn = QPushButton("Exit")
            skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def on_activate():
                key = key_input.text().strip()
                valid, msg = SecurityManager.validate_license(key)
                if valid:
                    status_label.setStyleSheet("color: green;")
                    status_label.setText("[OK] " + msg)
                    QMessageBox.information(
                        license_dialog,
                        "Success",
                        "License activated successfully!\nWelcome to NeuroROM AI."
                    )
                    license_dialog.accept()
                else:
                    status_label.setStyleSheet("color: red;")
                    status_label.setText("[ERROR] " + msg)

            def on_skip():
                QMessageBox.warning(
                    license_dialog,
                    "License Required",
                    "A valid license is required to use NeuroROM AI."
                )
                sys.exit(0)

            activate_btn.clicked.connect(on_activate)
            skip_btn.clicked.connect(on_skip)

            button_layout.addWidget(skip_btn)
            button_layout.addWidget(activate_btn)
            layout.addLayout(button_layout)

            license_dialog.exec()

    def update_window_title(self):
        self.setWindowTitle("NEUROROM AI V 7.0 PRO SUITE - Ultimate Translation Framework")

    def init_ui(self):
        self.setWindowTitle("NEUROROM AI V 7.0 PRO SUITE - Ultimate Translation Framework")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # --- NOVO: Configura o Menu Superior ---
        self.setup_menu()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_extraction_tab(), self.tr("tab1"))
        self.tabs.addTab(self.create_translation_tab(), self.tr("tab2"))
        self.tabs.addTab(self.create_reinsertion_tab(), self.tr("tab3"))

        # Create Graphics Lab tab (DESABILITADO - Em desenvolvimento)
        graphics_placeholder = QWidget()
        graphics_placeholder_layout = QVBoxLayout(graphics_placeholder)
        graphics_placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Título
        graphics_title = QLabel("🔧 Laboratório Gráfico")
        graphics_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFA500; margin-bottom: 10px;")
        graphics_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graphics_placeholder_layout.addWidget(graphics_title)

        # Mensagem de desenvolvimento
        graphics_msg = QLabel("Esta funcionalidade está em desenvolvimento e será habilitada em breve.")
        graphics_msg.setStyleSheet("font-size: 14px; color: #888888; padding: 20px;")
        graphics_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graphics_msg.setWordWrap(True)
        graphics_placeholder_layout.addWidget(graphics_msg)

        # Observação técnica
        graphics_tech_note = QLabel(
            "[WARN] Observação Técnica:\n\n"
            "O Laboratório Gráfico requer módulos adicionais de processamento de imagem\n"
            "(PIL/Pillow, OpenCV) e está sendo otimizado para melhor performance.\n\n"
            "Recursos planejados:\n"
            "• Visualização de tiles e sprites\n"
            "• Edição de fontes da ROM\n"
            "• OCR + Tradução automática de texturas\n"
            "• Exportação/Importação de gráficos"
        )
        graphics_tech_note.setStyleSheet("""
            font-size: 12px;
            color: #666666;
            background-color: #1a1a1a;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #333333;
        """)
        graphics_tech_note.setAlignment(Qt.AlignmentFlag.AlignLeft)
        graphics_tech_note.setWordWrap(True)
        graphics_placeholder_layout.addWidget(graphics_tech_note)

        graphics_placeholder_layout.addStretch()
        self.tabs.addTab(graphics_placeholder, self.tr("tab5"))

        self.tabs.addTab(self.create_settings_tab(), self.tr("tab4"))
        left_layout.addWidget(self.tabs)
        main_layout.addWidget(left_panel, 3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Log de Operações
        log_group = QGroupBox(self.tr("log"))
        log_group.setObjectName("log_group")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)
        # Fonte Monospace para o Log (Fica mais "Hacker/Dev")
        font_log = QFont("Consolas", 9)
        self.log_text.setFont(font_log)

        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        # ========== PAINEL DE TRADUÇÃO EM TEMPO REAL (LADO DIREITO) ==========
        realtime_group = QGroupBox("📺 Tradução em Tempo Real")
        realtime_group.setObjectName("realtime_translation_group")
        realtime_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #4CAF50;
            }
        """)
        realtime_layout = QVBoxLayout()

        self.realtime_original_label = QLabel("Original: Aguardando...")
        self.realtime_original_label.setStyleSheet("color: #FFC107; font-size: 11pt; padding: 8px;")
        self.realtime_original_label.setWordWrap(True)
        realtime_layout.addWidget(self.realtime_original_label)

        self.realtime_translated_label = QLabel("Tradução: ---")
        self.realtime_translated_label.setStyleSheet("color: #4CAF50; font-size: 11pt; font-weight: bold; padding: 8px;")
        self.realtime_translated_label.setWordWrap(True)
        realtime_layout.addWidget(self.realtime_translated_label)

        self.realtime_info_label = QLabel("⚡ Tradutor: --- | Aguardando início...")
        self.realtime_info_label.setStyleSheet("color: #888; font-size: 10pt; padding: 5px;")
        realtime_layout.addWidget(self.realtime_info_label)

        realtime_group.setLayout(realtime_layout)
        right_layout.addWidget(realtime_group)

        # --- ALTERAÇÃO: REMOVIDOS OS BOTÕES GIGANTES "REINICIAR" E "SAIR" DAQUI ---
        # Eles agora estão no Menu Superior "Arquivo".
        # Isso limpa o visual e deixa mais profissional.

        # Copyright Footer
        copyright_label = QLabel("Developed by Celso - Programador Solo | © 2026 All Rights Reserved")
        copyright_label.setObjectName("copyright_label")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color:#888;font-size:9pt;font-weight:bold; margin-top: 10px;")
        right_layout.addWidget(copyright_label)

        main_layout.addWidget(right_panel, 2)
        self.statusBar().showMessage("NeuroROM AI Ready")
        self.log("[START] Sistema v7.0 [RUNTIME INTELLIGENT] Iniciado - Modo Especialista")

    def create_extraction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. GRUPO DE PLATAFORMA
        platform_group = QGroupBox(self.tr("platform"))
        platform_layout = QHBoxLayout()
        self.platform_combo = QComboBox()
        self.platform_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.platform_combo.setMinimumHeight(30) # Altura padrão desktop
        first_ready_index = -1
        for idx, (platform_name, data) in enumerate(ProjectConfig.PLATFORMS.items()):
            platform_code = data.get("code", "")
            is_ready = data.get("ready", False)
            if platform_code == "separator":
                self.platform_combo.addItem(platform_name)
                self.platform_combo.model().item(self.platform_combo.count()-1).setEnabled(False)
            else:
                self.platform_combo.addItem(platform_name, platform_code)
                # Marca primeiro item habilitado
                if is_ready and first_ready_index == -1:
                    first_ready_index = self.platform_combo.count() - 1
        # Seleciona primeiro item habilitado (Master System)
        if first_ready_index >= 0:
            self.platform_combo.setCurrentIndex(first_ready_index)
        self.platform_combo.currentIndexChanged.connect(lambda: self.on_platform_selected())
        platform_layout.addWidget(self.platform_combo)
        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 1.5. AVISO "EM FASE DE TESTES"
        self.console_warning_widget = QWidget()
        console_warning_layout = QVBoxLayout(self.console_warning_widget)
        console_warning_layout.setContentsMargins(0, 10, 0, 10)
        warning_label = QLabel("🚧 Em fase de testes")
        warning_label.setStyleSheet("background-color: #4CAF50; color: white; font-size: 12pt; font-weight: bold; padding: 10px; border-radius: 6px;")
        warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        console_warning_layout.addWidget(warning_label)
        warning_text = QLabel("Esta plataforma está em desenvolvimento e será habilitada em breve")
        warning_text.setStyleSheet("background-color: #FF9800; color: white; font-size: 10pt; padding: 8px; border-radius: 6px;")
        warning_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning_text.setWordWrap(True)
        console_warning_layout.addWidget(warning_text)
        self.console_warning_widget.setVisible(False)
        layout.addWidget(self.console_warning_widget)

        # 2. GRUPO DE ARQUIVO ROM/JOGO
        rom_group = QGroupBox(self.tr("rom_file"))
        rom_layout = QVBoxLayout()

        rom_select_layout = QHBoxLayout()

        # --- CORREÇÃO DE SEMÂNTICA: Laranja/Amarelo quando vazio (Atenção) ---
        self.rom_path_label = QLabel("Nenhum arquivo selecionado")
        self.rom_path_label.setStyleSheet("color: #FFC107; font-weight: bold;") # Amarelo = Atenção
        rom_select_layout.addWidget(self.rom_path_label)

        self.select_rom_btn = QPushButton("📁 Selecionar ROM/Jogo")
        self.select_rom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_rom_btn.setMinimumHeight(30)
        self.select_rom_btn.clicked.connect(self.select_rom)

        rom_select_layout.addWidget(self.select_rom_btn)
        rom_layout.addLayout(rom_select_layout)

        # PAINEL DE ANÁLISE FORENSE
        self.forensic_analysis_btn = QPushButton("🔍 Análise Forense (Raio-X)")
        self.forensic_analysis_btn.setMinimumHeight(30) # Mais compacto
        self.forensic_analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forensic_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #222; color: #FF9800; border: 1px solid #FF9800;
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #333; }
            QPushButton:disabled { background-color: #111; color: #444; border: 1px solid #333; }
        """)
        self.forensic_analysis_btn.setEnabled(False)
        self.forensic_analysis_btn.clicked.connect(self.run_forensic_analysis)
        rom_layout.addWidget(self.forensic_analysis_btn)

        self.forensic_progress = QProgressBar()
        self.forensic_progress.setVisible(False)
        self.forensic_progress.setRange(0, 0) # Indeterminado
        rom_layout.addWidget(self.forensic_progress)

        # VISOR COM BARRA DE ROLAGEM PRETA
        self.engine_detection_scroll = QScrollArea()
        self.engine_detection_scroll.setWidgetResizable(True)
        self.engine_detection_scroll.setMinimumHeight(400)
        self.engine_detection_scroll.setMaximumHeight(400)

        # Barra de rolagem sempre visível
        self.engine_detection_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.engine_detection_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.engine_detection_scroll.setStyleSheet("""
            QScrollArea {
                border: 2px solid #FF9800;
                border-radius: 6px;
                background-color: #0a0a0a;
            }
            QScrollBar:vertical {
                background: #0a0a0a;
                width: 16px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                min-height: 40px;
                border-radius: 8px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.engine_detection_label = QLabel("🔍 Aguardando seleção de arquivo...")
        self.engine_detection_label.setWordWrap(True)
        self.engine_detection_label.setTextFormat(Qt.TextFormat.RichText)
        self.engine_detection_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.engine_detection_label.setMinimumHeight(600)  # Força o label a ter altura mínima maior
        self.engine_detection_label.setStyleSheet("color: #777; padding: 10px;")
        self.engine_detection_scroll.setWidget(self.engine_detection_label)
        rom_layout.addWidget(self.engine_detection_scroll)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        # 4. BOTÕES DE AÇÃO (CORRIGIDOS PARA DESKTOP SIZE)
        # Altura reduzida de 55 para 40px. Fonte de 14pt para 12pt.

        # # 4. BOTÕES DE AÇÃO (ATUALIZADOS v6.0)
        buttons_h_layout = QHBoxLayout()

        # Botão Extrair Texto da ROM
        self.extract_btn = QPushButton("📄 Extrair Textos")
        self.extract_btn.setMinimumHeight(40)
        self.extract_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 12pt; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555; }
        """)
        self.extract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.extract_btn.clicked.connect(self.extract_texts)
        buttons_h_layout.addWidget(self.extract_btn)

        # Botão Carregar Arquivo TXT Extraído
        self.load_txt_btn = QPushButton("📂 Carregar TXT Extraído")
        self.load_txt_btn.setMinimumHeight(40)
        self.load_txt_btn.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; font-size: 12pt; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555; }
        """)
        self.load_txt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_txt_btn.clicked.connect(self.load_extracted_txt_directly)
        buttons_h_layout.addWidget(self.load_txt_btn)

        layout.addLayout(buttons_h_layout)

        # Botão Otimizar Dados (Laranja)
        self.optimize_btn = QPushButton("🪄 Otimizar Dados")
        self.optimize_btn.setMinimumHeight(40)
        self.optimize_btn.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-size: 12pt; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555; }
        """)
        self.optimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.optimize_btn.clicked.connect(self.optimize_data) # Conectado ao seu método existente
        layout.addWidget(self.optimize_btn)

        # 5. BARRAS DE PROGRESSO
        self.extract_progress_bar = QProgressBar()
        self.extract_progress_bar.setFormat("Extração: %p%")
        self.extract_progress_bar.setFixedHeight(20) # Barra fina e elegante
        layout.addWidget(self.extract_progress_bar)

        self.optimize_progress_bar = QProgressBar()
        self.optimize_progress_bar.setFormat("Otimização: %p%")
        self.optimize_progress_bar.setFixedHeight(20)
        layout.addWidget(self.optimize_progress_bar)

        self.extract_status_label = QLabel("Aguardando início...")
        self.extract_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extract_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.extract_status_label)

        self.optimize_status_label = QLabel("Aguardando início...")
        self.optimize_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.optimize_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.optimize_status_label)

        layout.addStretch()
        return widget

    def create_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        file_group = QGroupBox(self.tr("file_to_translate"))
        file_group.setObjectName("file_to_translate_group")
        file_layout = QHBoxLayout()

        # Semântica: Cinza/Amarelo quando vazio
        self.trans_file_label = QLabel(self.tr("no_file"))
        self.trans_file_label.setObjectName("trans_file_label")
        self.trans_file_label.setStyleSheet("color: #FFC107;")
        file_layout.addWidget(self.trans_file_label)

        self.sel_file_btn = QPushButton(self.tr("select_file"))
        self.sel_file_btn.setMinimumHeight(30)
        self.sel_file_btn.setObjectName("sel_file_btn")
        self.sel_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sel_file_btn.clicked.connect(self.select_translation_input_file)
        file_layout.addWidget(self.sel_file_btn)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # ... (O código do lang_config_group e mode_group permanece igual, pode manter) ...
        # Se quiser colar o bloco inteiro para garantir, segue abaixo a continuação:

        lang_config_group = QGroupBox(self.tr("language_config"))
        lang_config_group.setObjectName("lang_config_group")
        lang_config_layout = QGridLayout()
        source_lang_label = QLabel(self.tr("source_language"))
        source_lang_label.setObjectName("source_lang_label")
        lang_config_layout.addWidget(source_lang_label, 0, 0)
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.source_lang_combo.addItems(self.get_all_translated_source_languages())
        lang_config_layout.addWidget(self.source_lang_combo, 0, 1)
        target_lang_label = QLabel(self.tr("target_language"))
        target_lang_label.setObjectName("target_lang_label")
        lang_config_layout.addWidget(target_lang_label, 1, 0)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
        lang_config_layout.addWidget(self.target_lang_combo, 1, 1)
        self.source_lang_combo.currentTextChanged.connect(self.on_source_language_changed)
        self.target_lang_combo.currentTextChanged.connect(self.on_target_language_changed)
        lang_config_group.setLayout(lang_config_layout)
        layout.addWidget(lang_config_group)

        mode_group = QGroupBox(self.tr("translation_mode"))
        mode_group.setObjectName("mode_group")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_combo.addItems([
            "⚡ Gemini (Google AI)",
            "🦙 Llama (Ollama Local)",
            "🤖 ChatGPT (OpenAI)"
        ])
        self.mode_combo.setCurrentIndex(0)  # Gemini como padrão
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Estilo e Gênero removidos - interface simplificada

        self.api_group = QGroupBox(self.tr("api_config"))
        self.api_group.setObjectName("api_group")
        self.api_group.setVisible(True)
        self.api_group.setMinimumHeight(140)
        api_layout = QGridLayout()
        api_layout.setSpacing(8)
        api_layout.setContentsMargins(10, 15, 10, 10)

        api_key_label = QLabel(self.tr("api_key"))
        api_key_label.setObjectName("api_key_label")
        api_key_label.setMinimumHeight(25)
        api_layout.addWidget(api_key_label, 0, 0)

        api_container = QWidget()
        api_container_layout = QHBoxLayout(api_container)
        api_container_layout.setContentsMargins(0, 0, 0, 0)
        api_container_layout.setSpacing(5)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setMinimumHeight(28)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.eye_btn = QPushButton("👁")
        self.eye_btn.setFixedSize(32, 28)
        self.eye_btn.setCheckable(True)
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self.toggle_api_visibility)
        self.eye_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #333;
                font-size: 14px;
                padding-bottom: 2px;
            }
            QPushButton:checked { background-color: #555; }
        """)
        api_container_layout.addWidget(self.api_key_edit)
        api_container_layout.addWidget(self.eye_btn)
        api_layout.addWidget(api_container, 0, 1)

        workers_label = QLabel(self.tr("workers"))
        workers_label.setObjectName("workers_label")
        workers_label.setMinimumHeight(25)
        api_layout.addWidget(workers_label, 1, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.workers_spin.setMinimumHeight(28)
        self.workers_spin.setMinimum(1)
        self.workers_spin.setMaximum(10)
        self.workers_spin.setValue(3)
        api_layout.addWidget(self.workers_spin, 1, 1)

        timeout_label = QLabel(self.tr("timeout"))
        timeout_label.setObjectName("timeout_label")
        timeout_label.setMinimumHeight(25)
        api_layout.addWidget(timeout_label, 2, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeout_spin.setMinimumHeight(28)
        self.timeout_spin.setMinimum(30)
        self.timeout_spin.setMaximum(300)
        self.timeout_spin.setValue(120)
        api_layout.addWidget(self.timeout_spin, 2, 1)

        cache_check = QCheckBox(self.tr("use_cache"))
        cache_check.setObjectName("cache_check")
        cache_check.setChecked(True)
        cache_check.setMinimumHeight(25)
        api_layout.addWidget(cache_check, 3, 0)

        # Botão Limpar Cache
        self.clear_cache_btn = QPushButton("🗑️ Limpar Cache")
        self.clear_cache_btn.setObjectName("clear_cache_btn")
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.setFixedHeight(28)
        self.clear_cache_btn.setToolTip("Remove traduções salvas para forçar retradução")
        self.clear_cache_btn.clicked.connect(self.clear_translation_cache)
        api_layout.addWidget(self.clear_cache_btn, 3, 1)

        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)

        translation_progress_group = QGroupBox(self.tr("translation_progress"))
        translation_progress_group.setObjectName("translation_progress_group")
        translation_progress_layout = QVBoxLayout()
        self.translation_progress_bar = QProgressBar()
        self.translation_progress_bar.setFormat("%p%")
        self.translation_progress_bar.setFixedHeight(20)
        translation_progress_layout.addWidget(self.translation_progress_bar)
        self.translation_status_label = QLabel(self.tr("waiting"))
        self.translation_status_label.setObjectName("translation_status_label")
        self.translation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_status_label.setStyleSheet("color: #666;")
        translation_progress_layout.addWidget(self.translation_status_label)
        translation_progress_group.setLayout(translation_progress_layout)
        layout.addWidget(translation_progress_group)

        # Botão TRADUZIR (Tamanho 40px)
        self.translate_btn = QPushButton(self.tr("translate_ai"))
        self.translate_btn.setObjectName("translate_btn")
        self.translate_btn.setMinimumHeight(40) # Ajustado
        self.translate_btn.setStyleSheet("""
            QPushButton{background-color:#2196F3;color:white;font-size:12pt;font-weight:bold;border-radius:6px;}
            QPushButton:hover{background-color:#1976D2;}
        """)
        self.translate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.translate_btn.clicked.connect(self.translate_texts)
        layout.addWidget(self.translate_btn)

        # Botão PARAR (Tamanho 40px)
        self.stop_translation_btn = QPushButton(self.tr("stop_translation"))
        self.stop_translation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_translation_btn.setObjectName("stop_translation_btn")
        self.stop_translation_btn.setMinimumHeight(40) # Ajustado
        self.stop_translation_btn.setStyleSheet("""
            QPushButton{background-color:#D32F2F;color:white;font-size:12pt;font-weight:bold;border-radius:6px;}
            QPushButton:hover{background-color:#B71C1C;}
            QPushButton:disabled{background-color:#333;color:#555;}
        """)
        self.stop_translation_btn.clicked.connect(self.stop_translation)
        self.stop_translation_btn.setEnabled(False)
        layout.addWidget(self.stop_translation_btn)

        layout.addStretch()
        return widget

    def create_reinsertion_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        rom_group = QGroupBox(self.tr("original_rom"))
        rom_group.setObjectName("reinsert_rom_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()

        self.reinsert_rom_label = QLabel(self.tr("no_rom"))
        self.reinsert_rom_label.setObjectName("reinsert_rom_label")
        self.reinsert_rom_label.setStyleSheet("color: #FFC107;") # Amarelo (Atenção)
        rom_select_layout.addWidget(self.reinsert_rom_label)

        select_reinsert_rom_btn = QPushButton(self.tr("select_rom"))
        select_reinsert_rom_btn.setObjectName("select_reinsert_rom_btn")
        select_reinsert_rom_btn.setMinimumHeight(30)
        select_reinsert_rom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_reinsert_rom_btn.clicked.connect(self.select_rom_for_reinsertion)
        rom_select_layout.addWidget(select_reinsert_rom_btn)
        rom_layout.addLayout(rom_select_layout)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        trans_group = QGroupBox(self.tr("translated_file"))
        trans_group.setObjectName("translated_file_group")
        trans_layout = QVBoxLayout()
        trans_select_layout = QHBoxLayout()

        self.translated_file_label = QLabel(self.tr("no_rom"))
        self.translated_file_label.setObjectName("translated_file_label")
        self.translated_file_label.setStyleSheet("color: #FFC107;") # Amarelo
        trans_select_layout.addWidget(self.translated_file_label)

        select_translated_btn = QPushButton(self.tr("select_file"))
        select_translated_btn.setObjectName("select_translated_btn")
        select_translated_btn.setMinimumHeight(30)
        select_translated_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_translated_btn.clicked.connect(self.select_translated_file)
        trans_select_layout.addWidget(select_translated_btn)
        trans_layout.addLayout(trans_select_layout)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        output_group = QGroupBox(self.tr("output_rom"))
        output_group.setObjectName("output_rom_group")
        output_layout = QVBoxLayout()
        self.output_rom_edit = QLineEdit()
        self.output_rom_edit.setPlaceholderText(self._build_output_placeholder_text())
        output_layout.addWidget(self.output_rom_edit)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        reinsertion_progress_group = QGroupBox(self.tr("reinsertion_progress"))
        reinsertion_progress_group.setObjectName("reinsertion_progress_group")
        reinsertion_progress_layout = QVBoxLayout()
        self.reinsertion_progress_bar = QProgressBar()
        self.reinsertion_progress_bar.setFormat("%p%")
        self.reinsertion_progress_bar.setFixedHeight(20)
        reinsertion_progress_layout.addWidget(self.reinsertion_progress_bar)
        self.reinsertion_status_label = QLabel(self.tr("waiting"))
        self.reinsertion_status_label.setObjectName("reinsertion_status_label")
        self.reinsertion_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reinsertion_status_label.setStyleSheet("color: #666;")
        reinsertion_progress_layout.addWidget(self.reinsertion_status_label)
        reinsertion_progress_group.setLayout(reinsertion_progress_layout)
        layout.addWidget(reinsertion_progress_group)

        self.reinsert_btn = QPushButton(self.tr("reinsert"))
        self.reinsert_btn.setObjectName("reinsert_btn")
        self.reinsert_btn.setMinimumHeight(40) # Ajustado
        self.reinsert_btn.setStyleSheet("""
            QPushButton{background-color:#FF9800;color:white;font-size:12pt;font-weight:bold;border-radius:6px;}
            QPushButton:hover{background-color:#F57C00;}
            QPushButton:disabled{background-color:#333;color:#555;}
        """)
        self.reinsert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reinsert_btn.clicked.connect(self.reinsert)
        layout.addWidget(self.reinsert_btn)

        layout.addStretch()
        return widget

    def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ui_lang_group = QGroupBox(self.tr("ui_language"))
        ui_lang_group.setObjectName("ui_lang_group")
        ui_lang_layout = QHBoxLayout()
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        self.ui_lang_combo.setMaxVisibleItems(15)
        self.ui_lang_combo.addItems(ProjectConfig.UI_LANGUAGES.keys())
        self.ui_lang_combo.setCurrentText("Português (PT-BR)")  # Define português como padrão
        self.ui_lang_combo.currentTextChanged.connect(self.change_ui_language)
        ui_lang_layout.addWidget(self.ui_lang_combo)
        ui_lang_group.setLayout(ui_lang_layout)
        layout.addWidget(ui_lang_group)

        theme_group = QGroupBox(self.tr("theme"))
        theme_group.setObjectName("theme_group")
        theme_layout = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        # Populate with translated theme names
        self.theme_combo.addItems(self.get_all_translated_theme_names())
        # Set current theme using translated name
        current_translated = self.get_translated_theme_name(self.current_theme)
        self.theme_combo.setCurrentText(current_translated)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        font_group = QGroupBox(self.tr("font_family"))
        font_group.setObjectName("font_group")
        font_layout = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        self.font_combo.addItems(ProjectConfig.FONT_FAMILIES.keys())
        self.font_combo.setCurrentText(self.current_font_family)
        self.font_combo.currentTextChanged.connect(self.change_font_family)
        font_layout.addWidget(self.font_combo)
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # COMMERCIAL GRADE: Ajuda e Suporte Section
        self.help_group = QGroupBox(self.tr("help_support"))
        self.help_group.setObjectName("help_group")
        help_layout = QFormLayout()

        # Guia de Uso Profissional Dropdown
        self.manual_label = QLabel(self.tr("manual_guide"))
        self.manual_combo = QComboBox()
        self.manual_combo.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        self.populate_manual_combo()  # [OK] Use logical IDs
        self.manual_combo.currentIndexChanged.connect(self.show_manual_step)

        help_layout.addRow(self.manual_label, self.manual_combo)

        # Contato para dúvidas
        self.contact_label = QLabel(
            f"<br><b>{self.tr('contact_support')}</b><br>"
            "<a href='mailto:celsoexpert@gmail.com' style='color: #4CAF50; text-decoration: none;'>"
            "celsoexpert@gmail.com</a>"
        )
        self.contact_label.setOpenExternalLinks(True)
        self.contact_label.setWordWrap(True)
        self.contact_label.setTextFormat(Qt.TextFormat.RichText)
        self.contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_layout.addRow("", self.contact_label)

        self.help_group.setLayout(help_layout)
        layout.addWidget(self.help_group)

        # PROFESSIONAL: Version label for buyer confidence
        layout.addStretch()
        version_label = QLabel("Versão do Sistema: v7.0 Stable")
        version_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        return widget

    # NOTE: create_graphics_lab_tab() has been moved to gui_tabs/graphic_lab.py

    def on_mode_changed(self, index: int):
        self.api_group.setVisible(index > 0)

    def keyPressEvent(self, event):
        """
        Intercepta eventos de teclado.
        Graphics Lab navigation is now handled by the GraphicLabTab itself.
        """
        # Delegate to graphics tab if it's the active tab
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 3:
            if self.graphics_lab_tab and hasattr(self.graphics_lab_tab, 'keyPressEvent'):
                self.graphics_lab_tab.keyPressEvent(event)
                return

        # Chama implementação padrão para outras teclas
        super().keyPressEvent(event)

    def populate_manual_combo(self):
        """Populate manual dropdown with translated items using logical IDs."""
        # Temporarily disconnect signal to prevent accidental auto-opening
        try:
            self.manual_combo.currentIndexChanged.disconnect(self.show_manual_step)
            signal_was_connected = True
        except:
            signal_was_connected = False

        # Repopulate combo (apenas funcionalidades ativas)
        self.manual_combo.clear()
        self.manual_combo.addItems([
            self.tr("manual_guide_title"),
            self.tr("manual_step_1"),
            self.tr("manual_step_2"),
            self.tr("manual_step_3"),
            self.tr("manual_step_4"),
            # "Laboratório Gráfico" e "Jogos de PC" removidos - em desenvolvimento
        ])

        # Ensure index is 0 (closed state)
        self.manual_combo.setCurrentIndex(0)

        # Reconnect signal if it was connected before
        if signal_was_connected:
            self.manual_combo.currentIndexChanged.connect(self.show_manual_step)

    def on_platform_selected(self, index=None):
        selected_text = self.platform_combo.currentText()
        data = ProjectConfig.PLATFORMS.get(selected_text)

        # Fallback para busca por conteúdo se necessário
        if not data:
            for k, v in ProjectConfig.PLATFORMS.items():
                if k in selected_text: data = v; break

        # Se for separador ou inválido, desativa
        if not data or data.get("code") == "separator":
            if hasattr(self, 'extract_btn'):
                self.extract_btn.setEnabled(False)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
            return

        is_ready = data.get("ready", False)

        # Mostrar/ocultar aviso de plataforma em desenvolvimento
        if hasattr(self, 'console_warning_widget'):
            self.console_warning_widget.setVisible(not is_ready)

        if hasattr(self, 'extract_btn'):
            if is_ready:
                # PLATAFORMA PRONTA
                self.extract_btn.setEnabled(True)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
                if hasattr(self, 'optimize_btn'): self.optimize_btn.setEnabled(True)
                if hasattr(self, 'select_rom_btn'): self.select_rom_btn.setEnabled(True)
                if hasattr(self, 'forensic_analysis_btn'): self.forensic_analysis_btn.setEnabled(True)
                self.log(f"[OK] Plataforma selecionada: {selected_text}")
            else:
                # PLATAFORMA EM FASE DE TESTES
                self.extract_btn.setEnabled(False)
                # Texto do Botão (Usa tradução)
                self.extract_btn.setText("🚧 " + self.tr("in_development"))
                # Tooltip ao passar o mouse (Usa tradução)
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))

                if hasattr(self, 'optimize_btn'):
                    self.optimize_btn.setEnabled(False)
                    self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

                if hasattr(self, 'select_rom_btn'):
                    self.select_rom_btn.setEnabled(False)

                if hasattr(self, 'forensic_analysis_btn'):
                    self.forensic_analysis_btn.setEnabled(False)

                self.log(f"🚧 {selected_text}: {self.tr('in_development')}")

    def change_ui_language(self, lang_name: str):
        self.current_ui_lang = ProjectConfig.UI_LANGUAGES[lang_name]
        self.refresh_ui_labels()
        self.save_config()
        self.log(f"Idioma alterado para: {lang_name}")

    def refresh_ui_labels(self):
        """Atualiza a interface gráfica quando o idioma é alterado."""
        self.update_window_title()

        # Tabs
        self.tabs.setTabText(0, self.tr("tab1"))
        self.tabs.setTabText(1, self.tr("tab2"))
        self.tabs.setTabText(2, self.tr("tab3"))
        self.tabs.setTabText(3, self.tr("tab5"))  # Graphics Lab agora no índice 3
        self.tabs.setTabText(4, self.tr("tab4"))  # Settings agora no índice 4

        # ═══════════════════════════════════════════════════════════
        # GRAPHICS LAB UI UPDATES (Tab 4 - i18n Support)
        # ═══════════════════════════════════════════════════════════

        # Atualizar a aba gráfica
        if self.graphics_lab_tab and hasattr(self.graphics_lab_tab, 'retranslate'):
            self.graphics_lab_tab.retranslate()

        # Update theme combo with translated names
        if hasattr(self, 'theme_combo'):
            # Temporarily disconnect to avoid triggering change event
            self.theme_combo.currentTextChanged.disconnect(self.change_theme)
            # Clear and repopulate with translated names
            self.theme_combo.clear()
            self.theme_combo.addItems(self.get_all_translated_theme_names())
            # Restore current selection with translated name
            current_translated = self.get_translated_theme_name(self.current_theme)
            self.theme_combo.setCurrentText(current_translated)
            # Reconnect the signal
            self.theme_combo.currentTextChanged.connect(self.change_theme)

        # Update output ROM placeholder with translated example filename
        if hasattr(self, 'output_rom_edit'):
            self.output_rom_edit.setPlaceholderText(self._build_output_placeholder_text())

        # Update source language combo with translated AUTO-DETECT
        if hasattr(self, 'source_lang_combo'):
            current_index = self.source_lang_combo.currentIndex()
            self.source_lang_combo.clear()
            self.source_lang_combo.addItems(self.get_all_translated_source_languages())
            self.source_lang_combo.setCurrentIndex(current_index)

        # Atualiza o título do grupo de Ajuda
        if hasattr(self, 'help_group'):
            self.help_group.setTitle(self.tr("help_support"))

        # Atualiza o texto do Guia
        if hasattr(self, 'manual_label'):
            self.manual_label.setText(self.tr("manual_guide"))

        def safe_update(object_name, widget_type, update_func):
            widget = self.findChild(widget_type, object_name)
            if widget:
                update_func(widget)

        # Manual dropdown
        if hasattr(self, 'populate_manual_combo'):
            self.populate_manual_combo()

        # Platform roadmap - REMOVED (not important for users)
        # if self.platform_combo and self.platform_combo.count() > 0:
        #     last_index = self.platform_combo.count() - 1
        #     self.platform_combo.setItemText(last_index, "📋 " + self.tr("roadmap_item"))

        # Buttons
        safe_update("btn_extract", QPushButton, lambda w: w.setText(self.tr("btn_extract")))
        safe_update("btn_optimize", QPushButton, lambda w: w.setText(self.tr("btn_optimize")))
        safe_update("stop_translation_btn", QPushButton, lambda w: w.setText(self.tr("stop_translation")))
        safe_update("reinsert_btn", QPushButton, lambda w: w.setText(self.tr("reinsert")))
        safe_update("extract_btn", QPushButton, lambda w: w.setText(self.tr("extract_texts")))
        safe_update("optimize_btn", QPushButton, lambda w: w.setText(self.tr("optimize_data")))
        safe_update("translate_btn", QPushButton, lambda w: w.setText(self.tr("translate_ai")))

        # Groups
        safe_update("platform_group", QGroupBox, lambda w: w.setTitle("Plataforma:"))
        safe_update("rom_file_group", QGroupBox, lambda w: w.setTitle(self.tr("rom_file")))
        safe_update("extract_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("extraction_progress")))
        safe_update("optimize_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("optimization_progress")))
        safe_update("file_to_translate_group", QGroupBox, lambda w: w.setTitle(self.tr("file_to_translate")))
        safe_update("lang_config_group", QGroupBox, lambda w: w.setTitle(self.tr("language_config")))
        safe_update("mode_group", QGroupBox, lambda w: w.setTitle(self.tr("translation_mode")))
        safe_update("api_group", QGroupBox, lambda w: w.setTitle(self.tr("api_config")))
        safe_update("translation_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("translation_progress")))
        safe_update("reinsert_rom_group", QGroupBox, lambda w: w.setTitle(self.tr("original_rom")))

        # Labels
        safe_update("rom_path_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.original_rom_path is None else None)
        safe_update("extract_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))
        safe_update("optimize_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))
        safe_update("trans_file_label", QLabel, lambda w: w.setText(self.tr("no_file")) if self.optimized_file is None else None)
        safe_update("source_lang_label", QLabel, lambda w: w.setText(self.tr("source_language")))
        safe_update("target_lang_label", QLabel, lambda w: w.setText(self.tr("target_language")))
        safe_update("api_key_label", QLabel, lambda w: w.setText(self.tr("api_key")))
        safe_update("workers_label", QLabel, lambda w: w.setText(self.tr("workers")))
        safe_update("timeout_label", QLabel, lambda w: w.setText(self.tr("timeout")))
        safe_update("translation_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))

        # Checkboxes
        safe_update("cache_check", QCheckBox, lambda w: w.setText(self.tr("use_cache")))

        # Button icons
        if self.select_rom_btn:
            self.select_rom_btn.setText(self.tr("select_rom"))
        if self.sel_file_btn:
            self.sel_file_btn.setText(self.tr("select_file"))

        # Update select reinsert ROM button with folder icon
        safe_update("select_reinsert_rom_btn", QPushButton, lambda w: w.setText(self.tr("select_rom")))

        safe_update("reinsert_rom_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.original_rom_path is None else None)
        safe_update("translated_file_group", QGroupBox, lambda w: w.setTitle(self.tr("translated_file")))
        safe_update("translated_file_label", QLabel, lambda w: w.setText(self.tr("no_rom")) if self.translated_file is None else None)

        # Update select translated file button with folder icon
        safe_update("select_translated_btn", QPushButton, lambda w: w.setText(self.tr("select_file")))
        safe_update("output_rom_group", QGroupBox, lambda w: w.setTitle(self.tr("output_rom")))
        safe_update("reinsertion_progress_group", QGroupBox, lambda w: w.setTitle(self.tr("reinsertion_progress")))
        safe_update("reinsertion_status_label", QLabel, lambda w: w.setText(self.tr("waiting")))

        # Update reinsert button with syringe icon
        safe_update("reinsert_btn", QPushButton, lambda w: w.setText("💉 " + self.tr("reinsert")))

        # Update tooltips for disabled platform buttons
        if hasattr(self, 'extract_btn'):
            current_tooltip = self.extract_btn.toolTip()
            # If button is disabled and has a tooltip, update it
            if not self.extract_btn.isEnabled() and current_tooltip:
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))
        if hasattr(self, 'optimize_btn'):
            current_tooltip = self.optimize_btn.toolTip()
            if not self.optimize_btn.isEnabled() and current_tooltip:
                self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

        safe_update("ui_lang_group", QGroupBox, lambda w: w.setTitle(self.tr("ui_language")))
        safe_update("theme_group", QGroupBox, lambda w: w.setTitle(self.tr("theme")))
        safe_update("font_group", QGroupBox, lambda w: w.setTitle(self.tr("font_family")))
        safe_update("help_group", QGroupBox, lambda w: w.setTitle(self.tr("help_support")))

        # Update manual label
        if self.manual_label:
            self.manual_label.setText(self.tr("manual_guide"))

        # Update contact label
        if hasattr(self, 'contact_label'):
            self.contact_label.setText(
                f"<br><b>{self.tr('contact_support')}</b><br>"
                "<a href='mailto:celsoexpert@gmail.com' style='color: #4CAF50; text-decoration: none;'>"
                "celsoexpert@gmail.com</a>"
            )

        safe_update("log_group", QGroupBox, lambda w: w.setTitle(self.tr("log")))

        # Update restart button with recycle icon
        safe_update("restart_btn", QPushButton, lambda w: w.setText("🔄 " + self.tr("restart")))

        # Update exit button with door icon
        safe_update("exit_btn", QPushButton, lambda w: w.setText("🚪 " + self.tr("exit")))
        safe_update("developer_label", QLabel, lambda w: w.setText(self.tr("developer")))

    # NOTE: retranslate_graphics_lab() has been moved to gui_tabs/graphic_lab.py

    def change_theme(self, theme_name: str):
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key
        ThemeManager.apply(QApplication.instance(), internal_key)
        self.save_config()
        self.log(f"Tema alterado para: {internal_key}")

    def change_font_family(self, font_name: str):
        self.current_font_family = font_name
        font_family_string = ProjectConfig.FONT_FAMILIES[font_name]
        primary_font = font_family_string.split(',')[0].strip()
        font = QFont()
        font.setFamily(primary_font)
        font.setPointSize(10)
        QApplication.instance().setFont(font)
        self.save_config()
        self.log(f"Fonte alterada para: {font_name}")

    def toggle_api_visibility(self, checked):
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.eye_btn.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.eye_btn.setText("👁️")

    def validate_file_platform_match(self, detected_engine, selected_platform_text):
        """
        Valida se o arquivo detectado é compatível com a plataforma selecionada.

        Returns:
            tuple: (is_valid: bool, error_message: str)
        """

        # Mapa: Nome da plataforma → Tipos/extensões aceitas
        platform_compatibility = {
            'Super Nintendo (SNES)': {
                'types': ['ROM'],
                'platforms': ['SNES ROM'],
                'extensions': ['.smc', '.sfc'],
                'engine': 'Console'
            },
            'Nintendo Entertainment System (NES)': {
                'types': ['ROM'],
                'platforms': ['NES ROM'],
                'extensions': ['.nes'],
                'engine': 'Console'
            },
            'Game Boy Advance (GBA)': {
                'types': ['ROM'],
                'platforms': ['Game Boy Advance ROM'],
                'extensions': ['.gba'],
                'engine': 'Console'
            },
            'Nintendo 64 (N64)': {
                'types': ['ROM'],
                'platforms': ['Nintendo 64 ROM'],
                'extensions': ['.z64', '.n64'],
                'engine': 'Console'
            },
            'Nintendo DS (NDS)': {
                'types': ['ROM'],
                'platforms': ['Nintendo DS ROM'],
                'extensions': ['.nds'],
                'engine': 'Console'
            },
            'Game Boy / Game Boy Color': {
                'types': ['ROM'],
                'platforms': ['Game Boy ROM', 'Game Boy Color ROM'],
                'extensions': ['.gb', '.gbc'],
                'engine': 'Console'
            },
            'PC Games (Windows)': {
                'types': ['PC_GAME'],
                'platforms': ['Doom WAD', 'PAK Archive', 'PC Executable', 'Unity Assets', 'JSON Data', 'RenPy Script'],
                'extensions': ['.exe', '.wad', '.pak', '.dat', '.assets', '.json', '.rpy', '.txt'],
                'engine': None  # Variável
            },
            'PlayStation 1 (PS1)': {
                'types': ['ROM'],
                'platforms': ['PlayStation/Genesis ROM', 'CD-ROM (PS1/PS2/GameCube/etc)'],
                'extensions': ['.bin', '.iso'],
                'engine': 'Console'
            },
        }

        # Plataformas em desenvolvimento (bloquear completamente)
        platforms_in_development = [
            'PlayStation 2 (PS2)',
            'PlayStation 3 (PS3)',
            'Sega Mega Drive',
            'Sega Master System',
            'Sega Dreamcast',
            'Xbox',
            'Xbox 360'
        ]

        # Verificar se plataforma está em desenvolvimento
        if selected_platform_text in platforms_in_development:
            error_msg = f"[ERROR] <b>Plataforma em Desenvolvimento</b><br><br>"
            error_msg += f"A plataforma <b>{selected_platform_text}</b> ainda não está disponível.<br><br>"
            error_msg += "[OK] <b>Plataformas disponíveis agora:</b><br>"
            error_msg += "• Super Nintendo (SNES)<br>"
            error_msg += "• Nintendo (NES)<br>"
            error_msg += "• Game Boy / GBA<br>"
            error_msg += "• PC Games (Windows)<br><br>"
            error_msg += "Por favor, selecione uma plataforma disponível."
            return False, error_msg

        # Obter compatibilidade da plataforma selecionada
        compatibility = platform_compatibility.get(selected_platform_text)

        if not compatibility:
            # Plataforma desconhecida ou não mapeada
            error_msg = f"[WARN] <b>Plataforma não reconhecida</b><br><br>"
            error_msg += f"Plataforma selecionada: <b>{selected_platform_text}</b><br><br>"
            error_msg += "Por favor, selecione uma plataforma válida do dropdown."
            return False, error_msg

        # Extrair informações da detecção
        detected_type = detected_engine.get('type', 'UNKNOWN')
        detected_platform = detected_engine.get('platform', 'Unknown')
        detected_extension = detected_engine.get('extension', '')

        # Verificar compatibilidade por tipo
        if detected_type not in compatibility['types']:
            # Tipo incompatível (ROM vs PC_GAME)
            if detected_type == 'PC_GAME' and 'ROM' in compatibility['types']:
                error_msg = f"[ERROR] <b>Arquivo Incompatível</b><br><br>"
                error_msg += f"<b>Plataforma selecionada:</b> {selected_platform_text} (Console ROM)<br>"
                error_msg += f"<b>Arquivo detectado:</b> {detected_platform} (Jogo de PC)<br><br>"
                error_msg += "🔧 <b>Soluções:</b><br>"
                error_msg += "1. Mude a plataforma para <b>'PC Games (Windows)'</b><br>"
                error_msg += "2. Ou selecione um arquivo ROM de console (.smc, .nes, .gba)"
                return False, error_msg
            elif detected_type == 'ROM' and 'PC_GAME' in compatibility['types']:
                error_msg = f"[ERROR] <b>Arquivo Incompatível</b><br><br>"
                error_msg += f"<b>Plataforma selecionada:</b> {selected_platform_text} (PC Games)<br>"
                error_msg += f"<b>Arquivo detectado:</b> {detected_platform} (ROM de Console)<br><br>"
                error_msg += "🔧 <b>Soluções:</b><br>"
                error_msg += "1. Mude a plataforma para o console correto (SNES, NES, etc.)<br>"
                error_msg += "2. Ou selecione um arquivo de jogo de PC (.wad, .exe, .pak)"
                return False, error_msg

        # Verificar compatibilidade por extensão (mais específico)
        if detected_extension and detected_extension not in compatibility['extensions']:
            # Extensão incompatível com a plataforma
            expected_ext = ', '.join(compatibility['extensions'])
            error_msg = f"[ERROR] <b>Formato de Arquivo Incompatível</b><br><br>"
            error_msg += f"<b>Plataforma selecionada:</b> {selected_platform_text}<br>"
            error_msg += f"<b>Extensões aceitas:</b> {expected_ext}<br>"
            error_msg += f"<b>Arquivo selecionado:</b> {detected_platform} ({detected_extension})<br><br>"
            error_msg += "🔧 <b>Solução:</b><br>"
            error_msg += f"Selecione um arquivo com extensão válida para {selected_platform_text}"
            return False, error_msg

        # Se chegou aqui, arquivo é compatível!
        return True, ""

    def select_rom(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar ROM/Jogo", "",
            "Todos os arquivos (*.*);;Arquivos de ROM (*.nes *.smc *.sfc *.gb *.gbc *.gba *.gen *.md *.iso *.bin *.img);;Arquivos PC (*.exe *.dll *.dat);;Arquivos de Texto (*.txt)"
        )
        if file_path:
            self.original_rom_path = file_path
            rom_size = os.path.getsize(file_path)
            crc32_full = _crc32_file(file_path)
            self.rom_path_label.setText(f"CRC32={crc32_full} | ROM_SIZE={rom_size}")
            self.rom_path_label.setStyleSheet("color: #4CAF50;")  # Verde = OK

            # HABILITA o botão de análise forense
            self.forensic_analysis_btn.setEnabled(True)

            self.log(f"[OK] ROM selecionada | CRC32={crc32_full} | ROM_SIZE={rom_size}")

            # Atualiza o label da aba de reinserção
            self.reinsert_rom_label.setText(f"CRC32={crc32_full} | ROM_SIZE={rom_size}")
            self.reinsert_rom_label.setStyleSheet("color: #4CAF50;")

            # Atualiza o campo de saída da ROM traduzida (nome do jogo + idioma alvo)
            rom_stem = Path(file_path).stem
            rom_ext = Path(file_path).suffix or ".rom"
            self.output_rom_edit.setText(f"{rom_stem}Pt-BR{rom_ext}")

            # [OK] Busca automática de arquivo extraído (usa nomes atuais e a pasta correta)
            rom_filename = crc32_full
            texts_dir = os.path.join(project_root, "texts")

            def _find_latest_in_texts(target_names):
                hits = []
                if os.path.isdir(texts_dir):
                    for root, _, files in os.walk(texts_dir):
                        for fn in files:
                            if fn in target_names:
                                hits.append(os.path.join(root, fn))
                if hits:
                    hits.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                    return hits[0]
                return None

            arquivo_encontrado = _find_latest_in_texts({
                f"{rom_filename}_clean_blocks.txt",
                f"{rom_filename}_extracted.txt",
                f"{rom_filename}_CLEAN_EXTRACTED.txt",
                f"{rom_filename}_V98_FORENSIC.txt",
                f"{rom_filename}_V9_EXTRACTED.txt",
                f"{rom_filename}_extracted_texts.txt",
            })

            if arquivo_encontrado:
                self.extracted_file = arquivo_encontrado
                # se for clean_blocks, salva também como last_clean_blocks
                if arquivo_encontrado.endswith("_clean_blocks.txt"):
                    self.last_clean_blocks = arquivo_encontrado

                self.trans_file_label.setText(os.path.basename(arquivo_encontrado))
                self.trans_file_label.setStyleSheet("color: #4CAF50;")
                self.log(f"📄 Arquivo extraído detectado: {os.path.basename(arquivo_encontrado)}")

                # [OK] Busca automática de arquivo otimizado (mais recente)
                opt = None
                if os.path.isdir(texts_dir):
                    opt_candidates = []
                    for root, _, files in os.walk(texts_dir):
                        for fn in files:
                            if fn.startswith(rom_filename) and ("OPTIMIZED" in fn.upper()):
                                opt_candidates.append(os.path.join(root, fn))
                    if opt_candidates:
                        opt_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        opt = opt_candidates[0]

                if opt and os.path.exists(opt):
                    self.optimized_file = opt
                    self.log(f"📄 Arquivo otimizado detectado: {os.path.basename(opt)}")

            elif self.extracted_file and os.path.exists(self.extracted_file):
                self.trans_file_label.setText(os.path.basename(self.extracted_file))
                self.trans_file_label.setStyleSheet("color: #4CAF50;")
        else:
            self.rom_path_label.setText("Nenhum arquivo selecionado")
            self.rom_path_label.setStyleSheet("color: #FFC107;")  # Amarelo = Atenção

            # DESABILITA o botão de análise forense
            self.forensic_analysis_btn.setEnabled(False)

    def executar_varredura_inteligente(self, path_obj):
        """Nova versão: Separa automaticamente Textos e Gráficos."""
        diretorio = path_obj.parent
        self.log(f"Minerando arquivos em: {diretorio}")

        # Extensões para as duas rotas
        ext_texto = ('.json', '.txt', '.xml', '.wad', '.msg', '.bin')
        ext_grafico = ('.png', '.dds', '.tga', '.bmp', '.jpg')

        lista_tiles = []
        arquivo_texto_principal = None

        for root, dirs, files in os.walk(diretorio):
            for file in files:
                caminho = os.path.join(root, file)
                ext = file.lower()

                # Rota 1: Vai para Strings/Otimização
                if ext.endswith(ext_texto):
                    if not arquivo_texto_principal:
                        arquivo_texto_principal = caminho

                # Rota 2: Vai para o Laboratório Gráfico
                elif ext.endswith(ext_grafico):
                    lista_tiles.append(caminho)

        # Envia os tiles encontrados para a sua interface de IA gráfica
        if lista_tiles:
            self.preencher_lista_laboratorio(lista_tiles)
            self.log(f"Sucesso: {len(lista_tiles)} tiles enviados ao Laboratório.")

        return arquivo_texto_principal

    def extrair_texto_de_imagem(self, caminho_da_imagem):
        """Esta função lê o texto de um botão ou menu do jogo (imagem)."""
        try:
            from PIL import Image
            import pytesseract

            # Abre a imagem selecionada
            img = Image.open(caminho_da_imagem)

            # Converte imagem em texto usando o motor OCR
            texto_detectado = pytesseract.image_to_string(img, lang='eng').strip()

            if texto_detectado:
                self.log(f"Texto extraído da imagem: {texto_detectado}")
                return texto_detectado
            return ""

        except Exception as e:
            self.log(f"Erro ao ler imagem: {_sanitize_error(e)}")
            return ""

    def detect_and_display_engine(self, file_path):
        """Detecta automaticamente o engine/tipo do arquivo e exibe informações formatadas na interface."""
        try:
            # Iniciar detecção
            self.log(self.tr("engine_detecting"))
            detection = detect_game_engine(file_path)

            # Armazenar resultado
            self.detected_engine = detection

            # Extrair dados com valores padrão
            tipo = detection.get("type", "UNKNOWN")
            plataforma = detection.get("platform", "Desconhecida")
            engine = detection.get("engine", "Desconhecida")
            observacoes = detection.get("notes", "")
            sugestao_conversor = detection.get("converter_suggestion", None)

            # Escolher emoji e cor
            if tipo == "ROM":
                emoji = "🟩"
                texto_tipo = self.tr("engine_rom")
                cor = "#4AC45F"  # Verde
            elif tipo == "PC_GAME":
                emoji = "🟦"
                texto_tipo = self.tr("engine_pc_game")
                cor = "#2196F3"  # Azul
            else:
                emoji = "🟧"
                texto_tipo = self.tr("engine_unknown")
                cor = "#FF8800"  # Laranja

            # Montar mensagem HTML
            mensagem = f"{emoji} <b>{self.tr('engine_detected')}</b>: {texto_tipo}<br>"
            mensagem += f"<b>{self.tr('engine_platform')}</b>: {plataforma}<br>"
            mensagem += f"<b>Engine:</b> {engine}<br>"

            if observacoes:
                mensagem += f"<br><small>{observacoes}</small>"

            if sugestao_conversor:
                mensagem += f"<br><br><b style='color:#4AC45F'>🔄 Conversor sugerido:</b> <code>{sugestao_conversor}</code>"

            # Atualizar interface
            self.engine_detection_label.setText(mensagem)
            self.engine_detection_label.setStyleSheet(
                f"color:black;padding:10px;border-radius:5px;border-left:3px solid {cor};"
            )
            self.engine_detection_scroll.setVisible(True)

            # Log detalhado
            self.log(f"🧠 Tipo detectado: {texto_tipo}")
            self.log(f"📦 Plataforma: {plataforma} | Engine: {engine}")

        except Exception as erro:
            self.log(f"[ERROR] Erro ao detectar engine: {erro}")
            self.engine_detection_scroll.setVisible(False)

    def detect_and_display_engine_async(self, file_path):
        """
        Detecção ULTRA-LEVE sem travar UI (COMERCIAL).
        Detecção completa só acontece ao clicar em 'Extrair'.
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return

            # Detecção LEVE apenas por extensão e tamanho (sem ler arquivo)
            file_ext = os.path.splitext(file_path)[1].lower()
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)

            # Mapeamento rápido por extensão
            if file_ext in ['.exe', '.dat']:
                # CORREÇÃO CRÍTICA: .exe > 100MB = Windows High-Capacity Binary
                if file_size_mb > 100:
                    engine = "Windows High-Capacity Binary"
                    platform = "PC (Windows)"
                    notes = f"Executável de grande porte ({file_size_mb:.1f} MB)"
                else:
                    engine = "Windows Executable"
                    platform = "PC (Windows)"
                    notes = f"Executável ({file_size_mb:.1f} MB)"

                type_emoji = "💻"
                type_text = "PC Game"
                color = "#2196F3"
                engine_type = 'PC_GAME'

            elif file_ext == '.wad':
                engine = "id Tech 1 (Doom Engine)"
                platform = "PC (DOS/Windows)"
                notes = "Classic FPS Engine (1993-1998)"
                type_emoji = "💻"
                type_text = "PC Game"
                color = "#2196F3"
                engine_type = 'PC_GAME'

            elif file_ext in ['.smc', '.sfc']:
                engine = "SNES Cartridge"
                platform = "Super Nintendo (16-bit)"
                notes = "Console clássico (1990-1996)"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = 'ROM'

            elif file_ext == '.nes':
                engine = "NES iNES Format"
                platform = "Nintendo Entertainment System"
                notes = "Console 8-bit (1983-1994)"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = 'ROM'

            elif file_ext in ['.gba', '.gb', '.gbc']:
                console_names = {'.gba': 'Game Boy Advance', '.gb': 'Game Boy', '.gbc': 'Game Boy Color'}
                platform = console_names.get(file_ext, 'Nintendo Handheld')
                engine = "Nintendo Handheld"
                notes = "Portátil Nintendo"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = 'ROM'

            elif file_ext in ['.iso', '.img', '.bin']:
                if file_size_mb > 600:
                    engine = "PS1 Game Disc"
                    platform = "PlayStation 1"
                    notes = "CD-ROM Image"
                else:
                    engine = "Binary Image"
                    platform = "Generic"
                    notes = f"Binary file ({file_size_mb:.1f} MB)"
                type_emoji = "💿"
                type_text = "Disc Image"
                color = "#FF9800"
                engine_type = 'ROM'

            else:
                engine = f"Binary File ({file_ext.upper()[1:]})"
                platform = "Generic"
                notes = f"Tamanho: {file_size_mb:.1f} MB"
                type_emoji = "📄"
                type_text = "Generic File"
                color = "#FF9800"
                engine_type = 'UNKNOWN'

            # Armazena detecção
            self.detected_engine = {
                'type': engine_type,
                'platform': platform,
                'engine': engine,
                'notes': notes
            }

            # Atualiza UI
            detection_text = f"{type_emoji} <b>Detectado:</b> {type_text}<br>"
            detection_text += f"<b>Plataforma:</b> {platform}<br>"
            detection_text += f"<b>Engine:</b> {engine}"
            if notes:
                detection_text += f"<br><small>{notes}</small>"

            self.engine_detection_label.setText(detection_text)
            self.engine_detection_label.setStyleSheet(f"color:{color};background:#1e1e1e;padding:10px;border-radius:5px;border-left:3px solid {color};")
            self.engine_detection_scroll.setVisible(True)

            # Log limpo
            self.log(f"🎯 Detectado: {type_text} | {platform}")
            self.log(f"📋 Engine: {engine}")

        except Exception as e:
            self.log(f"[WARN] Erro na detecção: {_sanitize_error(e)}")

    def start_engine_detection_async(self, file_path):
        """
        Inicia detecção de engine em thread separada (PERFORMANCE CRÍTICA).
        UI permanece 100% fluida durante análise de arquivos gigantes.
        """
        try:
            # Cancela detecção anterior se ainda estiver rodando
            if self.engine_detection_thread and self.engine_detection_thread.isRunning():
                self.engine_detection_thread.quit()
                self.engine_detection_thread.wait()

            # Cria novo worker (TIER 1 se disponível, senão fallback)
            if USE_TIER1_DETECTION:
                self.engine_detection_thread = EngineDetectionWorkerTier1(file_path)
                self.log("🔬 Usando sistema de detecção forense TIER 1")
            else:
                self.engine_detection_thread = EngineDetectionWorker(file_path)
                self.log("🔍 Usando sistema de detecção padrão")

            # Conecta signals
            self.engine_detection_thread.progress_signal.connect(self.on_engine_detection_progress)
            self.engine_detection_thread.detection_complete.connect(self.on_engine_detection_complete)

            # Exibe status inicial
            self.engine_detection_label.setText("🔬 Iniciando análise forense...")
            self.engine_detection_label.setStyleSheet("color:#FF9800;background:#1e1e1e;padding:10px;border-radius:5px;")
            self.engine_detection_scroll.setVisible(True)

            # Inicia thread
            self.engine_detection_thread.start()

        except Exception as e:
            self.log(f"[WARN] Erro ao iniciar detecção: {_sanitize_error(e)}")
            self.engine_detection_scroll.setVisible(False)

    def on_engine_detection_progress(self, status_text):
        """Handler de progresso da detecção (thread-safe via signal)."""
        self.engine_detection_label.setText(status_text)

    def on_engine_detection_complete(self, detection_result):
        """
        Handler chamado quando detecção TIER 1 termina (thread-safe via signal).

        TIER 1 UPGRADE: Exibe informações forenses completas:
        - Plataforma
        - Engine
        - Ano Estimado
        - Compressão (+ Entropia)
        - Confiança (Nível calculado)
        - Avisos e Recomendações
        """
        try:
            # Armazena resultado
            self.detected_engine = detection_result

            # ================================================================
            # EXTRAÇÃO DE INFORMAÇÕES FORENSES
            # ================================================================
            engine_type = detection_result.get('type', 'UNKNOWN')
            platform = detection_result.get('platform', 'Unknown')
            engine = detection_result.get('engine', 'Unknown')
            notes = detection_result.get('notes', '')

            # NOVOS CAMPOS TIER 1
            year_estimate = detection_result.get('year_estimate', None)
            compression = detection_result.get('compression', 'N/A')
            confidence = detection_result.get('confidence', 'N/A')
            entropy = detection_result.get('entropy', 0.0)
            warnings = detection_result.get('warnings', [])
            recommendations = detection_result.get('recommendations', [])

            # NOVOS CAMPOS TIER 1 ADVANCED (Contextual Fingerprinting)
            contextual_patterns = detection_result.get('contextual_patterns', [])
            architecture_inference = detection_result.get('architecture_inference', None)

            # NOVOS CAMPOS DEEP FINGERPRINTING (RAIO-X FORENSE)
            deep_analysis = detection_result.get('deep_analysis', None)

            # EXTRAÇÃO ANTECIPADA DO ANO DO JOGO (PRIORIDADE SOBRE INSTALADOR)
            game_year_from_deep = None
            if deep_analysis and deep_analysis.get('game_year'):
                game_year_from_deep = deep_analysis.get('game_year')
                # SOBRESCREVER year_estimate com ano do jogo (prioridade)
                year_estimate = game_year_from_deep

            # ================================================================
            # ESCOLHA DE EMOJI E COR POR TIPO
            # ================================================================
            type_emoji_map = {
                'ROM': ("🎮", "Console ROM", "#4CAF50"),
                'PC_GAME': ("💻", "PC Game", "#2196F3"),
                'PC_GENERIC': ("💻", "PC Executável", "#64B5F6"),
                'INSTALLER': ("[WARN]", "INSTALADOR", "#FF9800"),
                'ARCHIVE': ("📦", "Arquivo Compactado", "#9C27B0"),
                'ERROR': ("[ERROR]", "Erro", "#FF5722"),
                'UNKNOWN': ("❓", "Desconhecido", "#757575"),
                'GENERIC': ("📄", "Arquivo Genérico", "#FF9800")
            }

            type_emoji, type_text, color = type_emoji_map.get(
                engine_type,
                ("📄", "Arquivo Genérico", "#FF9800")
            )

            # ================================================================
            # MONTAGEM DA MENSAGEM EXPANDIDA (TIER 1)
            # ================================================================
            detection_text = f"{type_emoji} <b>Detectado:</b> {type_text}<br>"
            detection_text += f"<b>📍 Plataforma:</b> {platform}<br>"
            detection_text += f"<b>⚙️ Engine:</b> {engine}<br>"

            # ================================================================
            # INFORMAÇÕES DO HEADER SNES (SE DISPONÍVEL)
            # ================================================================
            snes_header_data = None
            for det in detection_result.get('detections', []):
                if det.get('category') == 'SNES_HEADER':
                    snes_header_data = det.get('snes_data')
                    break

            if snes_header_data:
                detection_text += f"<br><b>🎮 INFORMAÇÕES DA ROM SNES:</b><br>"
                detection_text += f"<b>📛 Título:</b> {snes_header_data.get('title', 'N/A')}<br>"
                # Neutralidade V1: não exibir metadados (title/region/map/cart). Identificar apenas por CRC32 e tamanho.
                try:
                    with open(rom_path, "rb") as _f:
                        _data = _f.read()
                    _crc32 = zlib.crc32(_data) & 0xFFFFFFFF
                    detection_text += f"<b>CRC32:</b> {_crc32:08X}<br>"
                    detection_text += f"<b>ROM_SIZE:</b> {len(_data)} bytes<br>"
                except Exception:
                    detection_text += f"<b>CRC32:</b> <i>Erro ao calcular</i><br>"
            # Ano Estimado
            if year_estimate:
                detection_text += f"<b>📅 Ano Estimado:</b> {year_estimate}<br>"
            else:
                detection_text += f"<b>📅 Ano Estimado:</b> <i>Não detectado</i><br>"

            # Compressão + Entropia
            detection_text += f"<b>🔧 Compressão:</b> {compression}<br>"

            # Confiança
            detection_text += f"<b>🎯 Confiança:</b> {confidence}<br>"

            # ================================================================
            # DEEP FINGERPRINTING (RAIO-X) - Exibição de features do jogo
            # ================================================================
            if deep_analysis and deep_analysis.get('patterns_found'):
                pattern_count = len(deep_analysis['patterns_found'])
                game_year_from_deep = deep_analysis.get('game_year')
                architecture_from_deep = deep_analysis.get('architecture_hints', [])
                features_from_deep = deep_analysis.get('feature_icons', [])

                detection_text += f"<br><b>🔬 RAIO-X DO INSTALADOR:</b> {pattern_count} padrões do jogo detectados<br>"

                # Mostrar arquitetura inferida do jogo
                if architecture_from_deep:
                    arch_name = architecture_from_deep[0]
                    detection_text += f"<b>🏗️ Jogo Detectado:</b> {arch_name}<br>"

                # Mostrar ano do jogo (não do instalador) - PRIORIDADE
                if game_year_from_deep:
                    detection_text += f"<b>📅 Ano do Jogo:</b> {game_year_from_deep}<br>"

                # Mostrar features detectadas (VERTICAL - um por linha)
                if features_from_deep:
                    detection_text += f"<br><b>🎮 Features Encontradas no Jogo:</b><br>"
                    for feature in features_from_deep[:10]:  # Máximo 10 features
                        detection_text += f"<small>• {feature}</small><br>"

            # ================================================================
            # CONTEXTUAL FINGERPRINTING (TIER 1 ADVANCED)
            # ================================================================
            if architecture_inference:
                arch_name = architecture_inference.get('architecture', 'N/A')
                game_type = architecture_inference.get('game_type', 'N/A')
                year_range = architecture_inference.get('year_range', 'N/A')
                based_on = architecture_inference.get('based_on', 'N/A')

                detection_text += f"<br><b>🏗️ Arquitetura Detectada:</b> {arch_name}<br>"
                detection_text += f"<b>[STATS] Tipo de Jogo:</b> {game_type}<br>"
                detection_text += f"<b>📅 Período:</b> {year_range}<br>"
                detection_text += f"<small><i>Baseado em: {based_on}</i></small><br>"

            # Padrões Contextuais Encontrados
            if contextual_patterns:
                detection_text += f"<br><b>🎯 Padrões Contextuais:</b> {len(contextual_patterns)} encontrados<br>"
                for pattern in contextual_patterns[:3]:  # Mostrar até 3 padrões
                    pattern_desc = pattern.get('description', 'N/A')
                    detection_text += f"<small>• {pattern_desc}</small><br>"

            # Notas técnicas (opcional)
            if notes:
                detection_text += f"<br><small><i>{notes}</i></small>"

            # ================================================================
            # AVISOS E RECOMENDAÇÕES (SE HOUVER)
            # ================================================================
            if warnings:
                detection_text += "<br><br><b>[WARN] AVISOS:</b><br>"
                for warning in warnings:
                    detection_text += f"<small>{warning}</small><br>"

            if recommendations:
                detection_text += "<br><b>💡 RECOMENDAÇÕES:</b><br>"
                for rec in recommendations:
                    detection_text += f"<small>{rec}</small><br>"

            # ================================================================
            # ATUALIZAÇÃO DA UI (THREAD-SAFE)
            # ================================================================
            self.engine_detection_label.setText(detection_text)
            self.engine_detection_label.setStyleSheet(
                f"""
                color: {color};
                background: #1e1e1e;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid {color};
                font-size: 10pt;
                """
            )
            self.engine_detection_scroll.setVisible(True)

            # ================================================================
            # LOG EXPANDIDO (TIER 1)
            # ================================================================
            self.log(f"🎯 Detectado: {type_text} | {platform}")
            self.log(f"📋 Engine: {engine}")

            if year_estimate:
                self.log(f"📅 Ano: {year_estimate}")

            self.log(f"🔧 Compressão: {compression}")
            self.log(f"🎯 Confiança: {confidence}")

            # Log de avisos
            for warning in warnings:
                self.log(warning)

            # ================================================================
            # SINCRONIZAÇÃO DO COMBOBOX DE PLATAFORMA
            # ================================================================
            platform_code = detection_result.get('platform_code')
            if platform_code and platform_code not in ['INSTALLER', 'ARCHIVE']:
                self.sync_platform_combobox(platform_code)
            else:
                # Para INSTALADORES e ARCHIVES, ocultar banner laranja de "em desenvolvimento"
                if hasattr(self, 'console_warning_widget'):
                    self.console_warning_widget.setVisible(False)
                # (Linhas acima...)
                if hasattr(self, 'console_warning_widget'):
                     self.console_warning_widget.setVisible(False)  #

            # ============================================================
            # FINALIZAÇÃO DA ANÁLISE FORENSE (MODO SEGURO)
            # ============================================================
            if hasattr(self, 'forensic_progress'):
                self.forensic_progress.setVisible(False)

            if hasattr(self, 'forensic_analysis_btn'):
                self.forensic_analysis_btn.setEnabled(True)

            # Limpa a referência da thread se ela existir
            if hasattr(self, 'engine_detection_thread'):
                self.engine_detection_thread = None

        except Exception as e:
            error_msg = f"[WARN] Erro ao processar detecção: {_sanitize_error(e)}"
            self.log(error_msg)

            # Mostra erro genérico
            self.engine_detection_label.setText(
                f"[ERROR] <b>Erro na Análise Forense</b><br>"
                f"<small>{error_msg}</small>"
            )
            self.engine_detection_label.setStyleSheet(
                "color:#FF5722;background:#1e1e1e;padding:10px;border-radius:5px;"
            )
            self.engine_detection_scroll.setVisible(True)

            # Finalizar análise mesmo em caso de erro
            self.forensic_progress.setVisible(False)
            self.forensic_analysis_btn.setEnabled(True)

    def sync_platform_combobox(self, platform_code):
        """
        Sincroniza o ComboBox de plataforma automaticamente com a detecção.

        MAPEAMENTO:
        - 'SNES' → Super Nintendo (SNES)
        - 'NES' → Nintendo (NES)
        - 'PS1' → PlayStation 1 (PS1)
        - 'GENESIS' → Sega Genesis / Mega Drive
        - 'GB'/'GBA' → Game Boy
        - 'PC' → Modo PC (sem mudança)
        """
        try:
            # Mapeamento de platform_code para texto do ComboBox
            platform_mapping = {
                'SNES': 'Super Nintendo (SNES)',
                'NES': 'Nintendo (NES)',
                'PS1': 'PlayStation 1 (PS1)',
                'GENESIS': 'Sega Genesis / Mega Drive',
                'GB': 'Game Boy (GB/GBC)',
                'GBA': 'Game Boy Advance (GBA)',
                'PC': 'PC Games (Windows)'  # Auto-seleciona PC Games
            }

            target_platform = platform_mapping.get(platform_code)

            if not target_platform:
                return  # Não faz nada para PC ou códigos desconhecidos

            # Procura pelo item no ComboBox
            for i in range(self.platform_combo.count()):
                item_text = self.platform_combo.itemText(i)

                # Verifica se encontrou a plataforma correta
                if target_platform in item_text or item_text.startswith(target_platform):
                    # Verifica se o item está habilitado
                    item = self.platform_combo.model().item(i)
                    if item and item.isEnabled():
                        self.platform_combo.setCurrentIndex(i)
                        self.log(f"[OK] ComboBox sincronizado: {item_text}")
                        return

            self.log(f"[WARN] Plataforma '{target_platform}' não encontrada no ComboBox")

        except Exception as e:
            self.log(f"[WARN] Erro ao sincronizar ComboBox: {_sanitize_error(e)}")

    def preencher_lista_laboratorio(self, lista_caminhos):
        """Envia imagens para o GraphicLabTab (CORRIGIDO - sem erro de widget)."""
        try:
            if self.graphics_lab_tab:
                # Muda para aba do Laboratório Gráfico
                if hasattr(self, 'tabs'):
                    self.tabs.setCurrentIndex(3)  # Índice 3 = Aba Graphics Lab

                self.log(f"[OK] {len(lista_caminhos)} gráficos detectados")
                self.log(f"💡 Use o botão '🎨 CARREGAR TEXTURA' no Laboratório Gráfico para visualizar")

                # Salva paths temporariamente para o usuário carregar manualmente
                temp_file = os.path.join(os.path.dirname(__file__), '..', '.pending_graphics.json')
                import json
                with open(temp_file, 'w') as f:
                    json.dump(lista_caminhos, f)

            else:
                self.log("[WARN] GraphicLabTab não disponível")
        except Exception as e:
            self.log(f"[ERROR] Erro ao processar gráficos: {_sanitize_error(e)}")
    def _is_supported_translation_input_path(self, file_path: str) -> bool:
        low = str(file_path or "").lower()
        return low.endswith(
            (
                "_pure_text_optimized.txt",
                "_only_safe_text.txt",
                "_only_safe_text_pure.txt",
                "_pure_text.jsonl",
            )
        )

    def _is_advanced_jsonl_input(self, file_path: str) -> bool:
        return str(file_path or "").lower().endswith("_pure_text.jsonl")

    def _normalize_path_key(self, file_path: str) -> str:
        return os.path.abspath(str(file_path or "")).replace("\\", "/").lower()

    def _is_advanced_jsonl_confirmed(self, file_path: str) -> bool:
        return self._normalize_path_key(file_path) == str(
            getattr(self, "_advanced_jsonl_confirmed_path", "") or ""
        )

    def _confirm_advanced_jsonl_translation(self, file_path: str) -> bool:
        if not self._is_advanced_jsonl_input(file_path):
            return True
        if self._is_advanced_jsonl_confirmed(file_path):
            return True
        answer = QMessageBox.warning(
            self,
            "Aviso",
            "Modo avançado: JSONL direto detectado.\n\n"
            "Esse modo pode mostrar ruído técnico no painel de tempo real.\n"
            "Para fluxo limpo, prefira *_pure_text_optimized.txt ou *_only_safe_text.txt.\n\n"
            "Deseja continuar em JSONL direto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._advanced_jsonl_confirmed_path = self._normalize_path_key(file_path)
            self.log(
                f"[ADV] JSONL direto confirmado: {os.path.basename(file_path)}"
            )
            return True
        return False

    def select_translation_input_file(self):
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if self.original_rom_path and os.path.exists(os.path.dirname(self.original_rom_path)):
            initial_dir = os.path.dirname(self.original_rom_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), initial_dir,
            "Arquivo para Tradução "
            "(*_pure_text_optimized.txt *_only_safe_text.txt "
            "*_only_safe_text_pure.txt *_pure_text.jsonl);;Todos os arquivos (*.*)"
        )

        if file_path:
            if not self._is_supported_translation_input_path(file_path):
                QMessageBox.warning(
                    self,
                    "Aviso",
                    "Selecione um destes arquivos:\n"
                    "- *_pure_text_optimized.txt\n"
                    "- *_only_safe_text.txt\n"
                    "- *_only_safe_text_pure.txt\n"
                    "- *_pure_text.jsonl (modo avançado)",
                )
                return

            fname_lower = os.path.basename(file_path).lower()
            path_normalized = file_path.replace("\\", "/").lower()
            if (
                "_interno" in path_normalized
                or "_all_text" in fname_lower
                or "_suspect" in fname_lower
            ):
                QMessageBox.warning(
                    self,
                    "Aviso",
                    "Arquivo interno/diagnóstico bloqueado.\n"
                    "Use apenas arquivos da trilha padrão (safe/optimized).",
                )
                return

            if self._is_advanced_jsonl_input(file_path):
                if not self._confirm_advanced_jsonl_translation(file_path):
                    return
            else:
                self._advanced_jsonl_confirmed_path = ""

            self.optimized_file = file_path
            txt_size = os.path.getsize(file_path)
            self.trans_file_label.setText(f"TXT ({txt_size} bytes)")
            self.trans_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.log(f"Arquivo carregado para tradução | FILE_SIZE={txt_size}")

            # Inferência de ROM desabilitada para neutralidade
            rom_directory = os.path.dirname(file_path)

    def load_extracted_txt_directly(self):
        """
        Carrega arquivo TXT já extraído e infere automaticamente a ROM original.
        Facilita quando usuário já tem o arquivo _CLEAN_EXTRACTED.txt pronto.
        """
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if self.original_rom_path and os.path.exists(os.path.dirname(self.original_rom_path)):
            initial_dir = os.path.dirname(self.original_rom_path)

        existing_file = getattr(self, "extracted_file", None)
        if existing_file and os.path.exists(existing_file):
            initial_dir = (
                os.path.dirname(existing_file)
                if os.path.isfile(existing_file)
                else existing_file
            )

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo TXT Extraído", initial_dir,
            "Extracted Text Files (*.txt *.jsonl "
            "*_pure_text_optimized.txt *_only_safe_text.txt *_only_safe_text_pure.txt "
            "*_pure_text.jsonl *_all_text.jsonl "
            "*_clean_blocks.txt *_extracted.txt *_CLEAN_EXTRACTED.txt *_V98_FORENSIC.txt *_V9_EXTRACTED.txt *_extracted_texts.txt);;"
            "All Files (*.*)"
        )

        if not file_path:
            return

        # Salva arquivo extraído
        self.extracted_file = file_path
        txt_size = os.path.getsize(file_path)
        self.trans_file_label.setText(f"TXT ({txt_size} bytes)")
        self.trans_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.log(f"[OK] Arquivo TXT carregado | FILE_SIZE={txt_size}")

        # Inferência de ROM desabilitada para neutralidade
        self.log("[INFO] Selecione a ROM manualmente na aba de reinserção")

    def select_rom_for_reinsertion(self):
        # ========== FILTROS DINÂMICOS POR PLATAFORMA (REINSERÇÃO) ==========
        selected_platform = self.platform_combo.currentText()

        # Mapeamento de plataformas para extensões (usa busca parcial para suportar anos)
        platform_filters = {
            "PC Games (Windows)": "PC Games (*.exe *.wad *.dat *.mtf *.box *.spt *.img)",
            "PlayStation 1": "PS1 Games (*.bin *.cue *.iso *.img *.pbp)",
            "Super Nintendo": "SNES ROMs (*.smc *.sfc *.fig *.swc)",
            "Nintendo (NES)": "NES ROMs (*.nes *.fds *.unf *.unif)",
            "Nintendo 64": "N64 ROMs (*.z64 *.n64 *.v64)",
            "Game Boy (1989)": "Game Boy ROMs (*.gb)",
            "Game Boy Color": "Game Boy Color ROMs (*.gbc)",
            "Game Boy Advance": "GBA ROMs (*.gba)",
            "Nintendo DS": "Nintendo DS ROMs (*.nds)",
            "Nintendo 3DS": "3DS ROMs (*.3ds *.cci *.cxi)",
            "Nintendo GameCube": "GameCube Images (*.iso *.gcm)",
            "Nintendo Wii (2006)": "Wii Images (*.iso *.wbfs *.wad)",
            "Nintendo Wii U": "Wii U Images (*.wux *.wud)",
            "Nintendo Switch": "Switch ROMs (*.nsp *.xci)",
            "PlayStation 2": "PS2 Images (*.iso *.bin)",
            "PlayStation 3": "PS3 Games (*.iso *.pkg)",
            "PlayStation 4": "PS4 Games (*.pkg)",
            "PlayStation 5": "PS5 Games (*.pkg)",
            "Sega Master System": "SMS ROMs (*.sms)",
            "Sega Mega Drive": "Mega Drive ROMs (*.md *.gen *.bin)",
            "Sega CD": "Sega CD Images (*.iso *.bin *.cue)",
            "Sega Saturn": "Saturn Images (*.iso *.bin *.cue)",
            "Sega Dreamcast": "Dreamcast Images (*.cdi *.gdi)",
            "MS-DOS": "DOS Games (*.exe *.com *.bat)",
            "Neo Geo": "Neo Geo ROMs (*.zip)",
            "Atari 2600": "Atari 2600 ROMs (*.a26 *.bin)",
            "Xbox Clássico": "Xbox Images (*.iso)",
            "Xbox 360": "Xbox 360 Images (*.iso *.xex)",
            "PC Games (Linux)": "Linux Games (*.x86 *.x86_64 *.sh)",
            "PC Games (Mac)": "Mac Games (*.app *.dmg)",
        }

        # Pega o filtro específico da plataforma (busca parcial para suportar anos)
        platform_filter = None
        for key, value in platform_filters.items():
            if key in selected_platform:
                platform_filter = value
                break

        if platform_filter:
            filtros = f"{platform_filter};;All Files (*.*)"
            self.log(f"🔍 Filtro de reinserção: {selected_platform}")
        else:
            filtros = (
                "All ROM Files (*.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds *.md *.exe *.bin *.iso);;"
                "PC Games (*.exe *.wad *.dat *.mtf *.box *.spt *.img);;"
                "Console ROMs (*.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds *.md);;"
                "All Files (*.*)"
            )
            self.log(f"🔍 Filtro genérico de reinserção")

        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), str(ProjectConfig.ROMS_DIR), filtros
        )
        if file_path:
            self.original_rom_path = file_path
            self.reinsert_rom_label.setText(Path(file_path).name)
            self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.rom_path_label.setText(Path(file_path).name)
            self.rom_path_label.setStyleSheet("color:#4CAF50;font-weight:bold;")

            # Habilitar botão de Análise Forense (Raio-X)
            self.forensic_analysis_btn.setEnabled(True)

            # Atualiza placeholder no padrão NomeDoJogo + idioma alvo + extensão
            file_ext = os.path.splitext(file_path)[1].lower()
            file_basename = Path(file_path).stem
            self.output_rom_edit.setPlaceholderText(
                self._build_output_placeholder_text(file_basename, file_ext or ".ext")
            )

    def _get_target_output_suffix(self) -> str:
        """Retorna o sufixo de idioma para nome da ROM de saída."""
        lang_code = str(getattr(self, "target_language_code", "") or "").strip().lower()
        if not lang_code:
            lang_code = "pt"
        suffix_map = {
            "pt": "Pt-BR",
            "en": "En-US",
            "es": "Es-ES",
            "fr": "Fr-FR",
            "de": "De-DE",
            "it": "It-IT",
            "ja": "Ja-JP",
            "ko": "Ko-KR",
            "zh": "Zh-CN",
            "ru": "Ru-RU",
        }
        return suffix_map.get(lang_code, lang_code.upper())

    def _build_output_placeholder_text(
        self,
        base_name: str | None = None,
        ext: str | None = None,
    ) -> str:
        """Monta placeholder de saída no padrão Ex: MeuJogoPt-BR.ext."""
        raw_name = str(base_name or "MeuJogo").strip()
        clean_name = re.sub(
            r"(?i)(?:[_\-\s]*(?:translated|traduzida?|pt-br|en-us|es-es|fr-fr|de-de|it-it|ja-jp|ko-kr|zh-cn|ru-ru))+$",
            "",
            raw_name,
        ).rstrip(" _-")
        if not clean_name:
            clean_name = "MeuJogo"
        suffix = self._get_target_output_suffix()
        if not clean_name.lower().endswith(suffix.lower()):
            clean_name = f"{clean_name}{suffix}"
        file_ext = str(ext or ".ext").strip()
        if not file_ext.startswith("."):
            file_ext = f".{file_ext}"
        return f"Ex: {clean_name}{file_ext}"

    def select_translated_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), str(ProjectConfig.ROMS_DIR),
            "Text Files (*.txt *.optimized.txt *.translated.txt);;All Files (*.*)"
        )
        if file_path:
            self.translated_file = file_path
            self.translated_file_label.setText(Path(file_path).name)
            self.translated_file_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"Translated file selected: {Path(file_path).name}")

    def reinsert(self):
        output_name = self.output_rom_edit.text().strip()
        if not self.original_rom_path or not os.path.exists(self.original_rom_path):
            QMessageBox.warning(self, "Aviso", "Selecione a ROM Original primeiro!")
            return
        if not self.translated_file or not os.path.exists(self.translated_file):
            QMessageBox.warning(self, "Aviso", "Arquivo Traduzido não encontrado!")
            return

        rom_path = self.original_rom_path
        translated_path = self.translated_file

        # ================================================================
        # PASTA DE SAÍDA SEGURA (evita Permission Denied em Program Files)
        # ================================================================
        # Usa pasta do arquivo TRADUZIDO em vez da pasta do jogo original
        # Isso evita erro de permissão em C:\Program Files
        safe_output_directory = os.path.dirname(translated_path)

        if output_name:
            output_rom_path = os.path.join(safe_output_directory, output_name)
        else:
            rom_ext = Path(rom_path).suffix
            rom_basename = Path(rom_path).stem
            output_rom_path = os.path.join(safe_output_directory, f"{rom_basename}Pt-BR{rom_ext or '.rom'}")

        self.log(f"📁 Pasta de saída segura: {safe_output_directory}")

        # SUPORTE EXPANDIDO: PC Games + ROMs de Console + Sega
        valid_extensions = ('.smc', '.sfc', '.bin', '.nes', '.z64', '.n64', '.gba', '.gb', '.gbc', '.nds', '.iso', '.exe', '.dll', '.dat', '.sms', '.md', '.gen', '.smd')
        if output_name and not output_name.lower().endswith(valid_extensions):
            QMessageBox.warning(self, "Erro", f"Extensão inválida. Use uma das: {', '.join(valid_extensions)}")
            return

        self.log(f"Starting reinsertion: {os.path.basename(rom_path)} -> {os.path.basename(output_rom_path)}")
        self.reinsertion_status_label.setText("Preparando arquivos...")
        self.reinsertion_progress_bar.setValue(0)
        self.reinsert_btn.setEnabled(False)

        self.reinsert_thread = ReinsertionWorker(rom_path, translated_path, output_rom_path)
        self.reinsert_thread.progress_signal.connect(self.reinsertion_progress_bar.setValue)
        self.reinsert_thread.status_signal.connect(self.reinsertion_status_label.setText)
        self.reinsert_thread.log_signal.connect(self.log)
        self.reinsert_thread.finished_signal.connect(self.on_reinsertion_finished)
        self.reinsert_thread.error_signal.connect(self.on_reinsertion_error)
        self.reinsert_thread.start()

    def on_reinsertion_finished(self):
        self.reinsertion_progress_bar.setValue(100)
        self.reinsert_btn.setEnabled(True)
        QMessageBox.information(self, self.tr("congratulations_title"), self.tr("congratulations_message"))

    def on_reinsertion_error(self, error_msg):
        self.reinsertion_status_label.setText("Erro!")
        self.reinsert_btn.setEnabled(True)
        self.log(f"[ERROR] Erro fatal na reinserção: {error_msg}")
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro na reinserção:\n{error_msg}")
    def extract_texts(self):
        """Função do Botão Verde: Extrai os textos da ROM original."""
        if not hasattr(self, 'original_rom_path') or not self.original_rom_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro!")
            return

        self.log("[START] Iniciando extração (identificação por CRC32/ROM_SIZE no report)")
        self.extract_progress_bar.setValue(0)

        # Aqui o sistema chama o motor de extração que já tínhamos
        try:
            # Se for SNES, usa a lógica de ponteiros, senão usa Scan Universal
            self.start_extraction_process()
        except Exception as e:
            self.log(f"[ERROR] Erro na extração: {_sanitize_error(e)}")
    def start_extraction_process(self):
        """Inicia o extrator apropriado baseado na plataforma selecionada."""
        # Calcula CRC32 para naming neutro
        self._extraction_crc32 = _crc32_file(self.original_rom_path)
        rom_size = os.path.getsize(self.original_rom_path)
        self.log(f"[START] Preparando extração | CRC32={self._extraction_crc32} | ROM_SIZE={rom_size}")
        self.extract_status_label.setText("Iniciando extração...")
        self.extract_progress_bar.setValue(10)

        import subprocess

        # Detecta plataforma pela extensão ou seleção
        file_ext = os.path.splitext(self.original_rom_path)[1].lower()
        selected_platform = self.platform_combo.currentText() if hasattr(self, 'platform_combo') else ""

        current_dir = os.path.dirname(os.path.abspath(__file__))

        # ========== SEGA MASTER SYSTEM / MEGA DRIVE ==========
        if file_ext == '.sms' or "Sega Master System" in selected_platform:
            self.log("🎮 Detectado: Sega Master System - Usando Sega Extractor")
            script_path = os.path.join(current_dir, "..", "core", "sega_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(os.path.dirname(current_dir), "core", "sega_extractor.py")
            self._current_extractor_type = "sega"
        elif file_ext in ['.md', '.gen', '.bin', '.smd'] or "Sega Mega Drive" in selected_platform:
            self.log("🎮 Detectado: Sega Mega Drive/Genesis - Usando Sega Extractor")
            script_path = os.path.join(current_dir, "..", "core", "sega_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(os.path.dirname(current_dir), "core", "sega_extractor.py")
            self._current_extractor_type = "sega"
        else:
            # ========== FALLBACK: FAST CLEAN EXTRACTOR ==========
            script_path = os.path.join(current_dir, "core", "fast_clean_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(os.path.dirname(current_dir), "core", "fast_clean_extractor.py")
            self._current_extractor_type = "fast_clean"

        if not os.path.exists(script_path):
            self.log(f"[ERROR] ERRO: Extrator não encontrado: {script_path}")
            return

        # 2. Executa o comando
        cmd = f'python "{script_path}" "{self.original_rom_path}"'
        # =========================
        # V6 PRO: SMS usa SegaExtractor (ponteiros + confiança)
        # =========================
        ext = os.path.splitext(self.original_rom_path)[1].lower()

        if ext == ".sms":
            """
            Quando a ROM é Master System (.sms), tenta usar o UniversalMasterSystemExtractor
            (que utiliza o banco de dados completo e heurísticas) para extrair todos os textos.
            Caso não esteja disponível ou ocorra um erro, faz fallback para o SegaExtractor
            padrão de ponteiros para manter compatibilidade.
            """
            # Tenta usar o extrator universal se disponível
            if UniversalMasterSystemExtractor:
                self.log("🧠 Extração Universal (Master System) ativada")
                try:
                    uni_extractor = UniversalMasterSystemExtractor(self.original_rom_path)
                    total = uni_extractor.extract_all()
                    if total > 0:
                        # Salva resultados na mesma pasta da ROM
                        output_file = uni_extractor.save_results()
                        self.log(f"[OK] SUCESSO: {total} textos extraídos.")
                        self.log(f"📁 Arquivo salvo: {output_file}")
                        # [OK] Guarda o caminho real do arquivo gerado
                        self.extracted_file = output_file
                        self.last_clean_blocks = output_file
                        try:
                            os.startfile(os.path.dirname(output_file))  # abre a pasta de saída
                        except Exception:
                            pass
                    else:
                        self.log("[WARN] Universal: Nenhum texto encontrado.")
                    # CORREÇÃO: Finaliza a UI corretamente
                    self.extract_progress_bar.setValue(100)
                    self.extract_status_label.setText("Concluído!")
                    self.extract_btn.setEnabled(True)
                    return
                except Exception as ex:
                    self.log(f"[ERROR] Erro ao usar UniversalMasterSystemExtractor: {ex}")
                    # Em caso de erro, continua para fallback abaixo
            # Fallback: usa SegaExtractor baseado em ponteiros
            self.log("🧠 Extração PRO baseada em ponteiros ativada (fallback)")
            try:
                from core.sega_extractor import SegaExtractor
                sega_extractor = SegaExtractor(self.original_rom_path)
                texts = sega_extractor.extract_texts(min_length=4)
                if not texts:
                    self.log("[WARN] SMS PRO: Nenhum texto confiável encontrado.")
                    self.extract_progress_bar.setValue(100)
                    self.extract_status_label.setText("Concluído (sem textos)")
                    self.extract_btn.setEnabled(True)
                    return
                self.log(f"[OK] SUCESSO: {len(texts)} strings reais extraídas.")
                self.log("🔍 PRÉVIA DOS TEXTOS:")
                for item in texts[:10]:
                    self.log(f"   [{item.get('offset_hex', hex(item.get('offset', 0)))}] {item.get('text','')}")
                # CORREÇÃO: Finaliza a UI corretamente
                self.extract_progress_bar.setValue(100)
                self.extract_status_label.setText("Concluído!")
                self.extract_btn.setEnabled(True)
                return
            except Exception as ex2:
                self.log(f"[ERROR] Erro ao usar SegaExtractor: {ex2}")
                self.extract_progress_bar.setValue(100)
                self.extract_status_label.setText("Erro!")
                self.extract_btn.setEnabled(True)
                return

        try:
            self.log(f"[START] Rodando extrator: {os.path.basename(script_path)} ... (Aguarde)")
            # Guarda o processo numa variável self.current_process para monitorar
            self.current_process = subprocess.Popen(cmd, shell=True)

            self.extract_progress_bar.setValue(50)
            self.extract_status_label.setText("Processando...")

            # 3. CRIA O MONITOR (O Segredo para não travar)
            self.v9_timer = QTimer()
            self.v9_timer.timeout.connect(self.check_v9_status)
            self.v9_timer.start(1000) # Verifica a cada 1 segundo (1000ms)

        except Exception as e:
            self.log(f"[ERROR] Erro ao lançar: {_sanitize_error(e)}")
    def check_v9_status(self):
        """Verifica se o processo de extração terminou e lê o relatório para o log."""
        if hasattr(self, 'current_process') and self.current_process.poll() is not None:
            self.v9_timer.stop()
            self.extract_progress_bar.setValue(100)
            self.extract_status_label.setText("Concluído!")

            # --- LÓGICA DE RECUPERAÇÃO DE RESULTADOS (NEUTRAL) ---
            rom_dir = os.path.dirname(self.original_rom_path)
            crc32_id = getattr(self, '_extraction_crc32', None)
            if not crc32_id:
                crc32_id = _crc32_file(self.original_rom_path)

            # Report file com naming neutro (CRC32)
            report_file = os.path.join(rom_dir, f"{crc32_id}_report.txt")

            # Verifica qual extrator foi usado e procura o arquivo correto
            extractor_type = getattr(self, '_current_extractor_type', 'fast_clean')

            # Lista de possíveis arquivos de saída - prioriza CRC32, fallback legacy
            possible_outputs = [
                # Novos nomes neutros (CRC32)
                os.path.join(rom_dir, f"{crc32_id}_pure_text.jsonl"),
                os.path.join(rom_dir, f"{crc32_id}_extracted.txt"),
            ]

            extracted_file = None
            for candidate in possible_outputs:
                if os.path.exists(candidate):
                    extracted_file = candidate
                    break

            # 1. Tenta ler o RELATÓRIO para o Log da direita
            if os.path.exists(report_file):
                self.log("="*40)
                self.log("📋 RESUMO DA EXTRAÇÃO:")
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip() and not line.startswith('#'):
                                self.log(f"  {line.strip()}")
                except Exception as e:
                    self.log(f"[WARN] Erro ao ler relatório: {_sanitize_error(e)}")
                self.log("="*40)

            # 2. Tenta mostrar uma prévia das strings no log
            if extracted_file:
                self.extracted_file = extracted_file
                file_size = os.path.getsize(extracted_file)
                self.trans_file_label.setText(f"TXT ({file_size} bytes)")
                self.trans_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

                # Conta quantas linhas tem
                try:
                    with open(extracted_file, 'r', encoding='utf-8') as f:
                        linhas = f.readlines()
                        total = len([l for l in linhas if l.startswith('[0x') or l.startswith('{')])
                        self.log(f"[OK] SUCESSO: {total} strings reais extraídas.")

                        # Mostra as 5 primeiras para dar um "gosto" no log
                        self.log("🔍 PRÉVIA DOS TEXTOS:")
                        amostra = [l.strip() for l in linhas if l.startswith('[0x') or l.startswith('{')][:5]
                        for a in amostra:
                            self.log(f"   {a}")
                except:
                    pass

                self.optimize_btn.setEnabled(True)
                platform_name = "Sega" if extractor_type == "sega" else "ROM"
                QMessageBox.information(self, "Extração Finalizada", f"Extração {platform_name} concluída!\nCRC32={crc32_id} | {total} strings")
            else:
                self.log("[ERROR] ERRO: O arquivo extraído não foi gerado.")

    def run_batch_test(self):
        """Executa teste comparativo V 9.5 em múltiplas ROMs"""
        from PyQt6.QtWidgets import QMessageBox

        self.log("🧪 Iniciando Teste em Lote V9.5...")

        # Mostra diálogo de confirmação
        reply = QMessageBox.question(
            self,
            "Teste em Lote V 9.0",
            "Este teste irá processar todas as ROMs encontradas nas subpastas.\n\n"
            "O processo pode demorar alguns minutos dependendo da quantidade de ROMs.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            self.log("[ERROR] Teste em lote cancelado pelo usuário.")
            return

        # Desabilita botões durante o processo
        self.batch_test_btn.setEnabled(False)
        self.extract_btn.setEnabled(False)
        self.optimize_btn.setEnabled(False)

        self.extract_status_label.setText("Executando teste em lote...")
        self.extract_progress_bar.setValue(10)

        import subprocess
        import sys

        # Localiza o script de teste em lote
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        batch_script = os.path.join(project_root, "test_v9_batch.py")

        if not os.path.exists(batch_script):
            self.log(f"[ERROR] ERRO: Script test_v9_batch.py não encontrado em {batch_script}")
            QMessageBox.critical(
                self,
                "Erro",
                f"Script de teste em lote não encontrado!\n\nProcurado em:\n{batch_script}"
            )
            self.batch_test_btn.setEnabled(True)
            self.extract_btn.setEnabled(True)
            self.optimize_btn.setEnabled(True)
            return

        try:
            self.log(f"[START] Executando: {os.path.basename(batch_script)}")
            self.log("⏳ Aguarde... O processo pode demorar alguns minutos.")

            # Executa o script de forma assíncrona
            self.batch_process = subprocess.Popen(
                [sys.executable, batch_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Cria timer para monitorar o processo
            self.batch_timer = QTimer()
            self.batch_timer.timeout.connect(self.check_batch_status)
            self.batch_timer.start(1000)  # Verifica a cada 1 segundo

            self.extract_progress_bar.setValue(50)

        except Exception as e:
            self.log(f"[ERROR] Erro ao iniciar teste em lote: {_sanitize_error(e)}")
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar teste em lote:\n{_sanitize_error(e)}")
            self.batch_test_btn.setEnabled(True)
            self.extract_btn.setEnabled(True)
            self.optimize_btn.setEnabled(True)

    def check_batch_status(self):
        """Monitora o progresso do teste em lote"""
        if self.batch_process.poll() is not None:
            # Processo terminou
            self.batch_timer.stop()

            # Lê a saída
            stdout, stderr = self.batch_process.communicate()

            if self.batch_process.returncode == 0:
                self.extract_progress_bar.setValue(100)
                self.extract_status_label.setText("Teste em lote concluído!")
                self.log("[OK] Teste em lote V 9.5 concluído com sucesso!")

                # Procura pelo arquivo de relatório
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                results_dir = os.path.join(project_root, "resultados_v9_comparativo")

                if os.path.exists(results_dir):
                    # Pega o relatório mais recente
                    reports = sorted(
                        [f for f in os.listdir(results_dir) if f.startswith("relatorio_comparativo_v9_")],
                        reverse=True
                    )

                    if reports:
                        latest_report = os.path.join(results_dir, reports[0])
                        self.log(f"[STATS] Relatório gerado: {reports[0]}")

                        # Mostra mensagem de sucesso com opção de abrir relatório
                        reply = QMessageBox.question(
                            self,
                            "Sucesso",
                            f"Teste em lote concluído!\n\n"
                            f"Relatório salvo em:\n{results_dir}\n\n"
                            f"Deseja abrir o relatório?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )

                        if reply == QMessageBox.StandardButton.Yes:
                            import platform
                            if platform.system() == 'Windows':
                                os.startfile(latest_report)
                            elif platform.system() == 'Darwin':  # macOS
                                subprocess.Popen(['open', latest_report])
                            else:  # Linux
                                subprocess.Popen(['xdg-open', latest_report])
                    else:
                        QMessageBox.information(
                            self,
                            "Concluído",
                            "Teste em lote concluído!\n\nVerifique a pasta resultados_v8_comparativo."
                        )
                else:
                    QMessageBox.information(
                        self,
                        "Concluído",
                        "Teste em lote concluído!"
                    )
            else:
                self.extract_progress_bar.setValue(0)
                self.extract_status_label.setText("Erro no teste em lote")
                self.log(f"[ERROR] Erro no teste em lote (código {self.batch_process.returncode})")
                if stderr:
                    self.log(f"Erro: {stderr}")

                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro durante o teste em lote.\n\nVerifique o log para mais detalhes."
                )

            # Reabilita botões
            self.batch_test_btn.setEnabled(True)
            self.extract_btn.setEnabled(True)
            self.optimize_btn.setEnabled(True)

    def optimize_data(self):
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Nenhuma ROM selecionada!")
            return

        # [OK] Usa o arquivo real gerado pela extração
        rom_filename = os.path.splitext(os.path.basename(self.original_rom_path))[0]

        input_file = None
        for attr in ("last_clean_blocks", "extracted_file"):
            p = getattr(self, attr, None)
            if p and os.path.exists(p):
                input_file = p
                break

        # Fallback: tenta achar automaticamente na pasta texts do projeto
        if not input_file:
            try:
                texts_dir = os.path.join(project_root, "texts")
                if os.path.isdir(texts_dir):
                    candidates = []
                    for root, _, files in os.walk(texts_dir):
                        for fn in files:
                            if fn in (f"{rom_filename}_clean_blocks.txt", f"{rom_filename}_extracted.txt"):
                                candidates.append(os.path.join(root, fn))
                    if candidates:
                        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        input_file = candidates[0]
            except Exception:
                pass

        if not input_file:
            QMessageBox.warning(self, "Erro", f"Arquivo de extração não encontrado para:\n{rom_filename}\n\nClique em 'Extrair Textos' primeiro.")
            return

        self.extracted_file = input_file # Atualiza para as próximas etapas
        self.optimize_status_label.setText("Analyzing...")
        self.optimize_progress_bar.setValue(0)
        self.optimize_btn.setEnabled(False)

        # [OK] PASSA AS CONFIGURAÇÕES DO OTIMIZADOR V 9.5
        self.optimize_thread = OptimizationWorker(input_file, is_pc_game=False, config=self.optimizer_config)
        self.optimize_thread.progress_signal.connect(self.optimize_progress_bar.setValue)
        self.optimize_thread.status_signal.connect(self.optimize_status_label.setText)
        self.optimize_thread.log_signal.connect(self.log)
        self.optimize_thread.finished_signal.connect(self.on_optimization_finished)
        self.optimize_thread.error_signal.connect(self.on_optimization_error)
        self.optimize_thread.start()

    def on_optimization_finished(self, output_file: str):
        self.optimized_file = output_file
        self.trans_file_label.setText(os.path.basename(output_file))
        self.trans_file_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.optimize_btn.setEnabled(True)
        self.tabs.setTabEnabled(1, True)

        # Recarrega o arquivo otimizado e atualiza o contador de linhas
        try:
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                optimized_lines = f.readlines()

            line_count = len(optimized_lines)
            self.log(f"[STATS] Arquivo otimizado carregado: {line_count:,} linhas")

            # Atualiza interface para mostrar o novo arquivo
            self.optimize_status_label.setText(f"Concluído! ({line_count:,} linhas)")

        except Exception as e:
            self.log(f"[WARN] Erro ao contar linhas: {_sanitize_error(e)}")

        QMessageBox.information(self, "Sucesso", f"Optimization completed!\nFile: {os.path.basename(output_file)}\nLines: {line_count:,}")

    def on_optimization_error(self, error_msg: str):
        self.optimize_status_label.setText("Erro!")
        self.optimize_btn.setEnabled(True)
        self.log(f"[ERROR] Erro na otimização: {error_msg}")
        QMessageBox.critical(self, "Erro", f"Optimization error:\n{error_msg}")

    def on_extract_finished(self, success: bool, message: str):
        if success:
            self.extract_status_label.setText("Concluído!")
            self.extract_progress_bar.setValue(100)

            try:
                rom_name = os.path.basename(self.original_rom_path).rsplit('.', 1)[0]
                rom_dir = os.path.dirname(self.original_rom_path)
                extracted_file_path = os.path.join(rom_dir, f"{rom_name}_extracted_texts.txt")

                if os.path.exists(extracted_file_path):
                    self.extracted_file = extracted_file_path
                    self.trans_file_label.setText(os.path.basename(extracted_file_path))
                    self.trans_file_label.setStyleSheet("color: #FF9800; font-weight: bold;")
                    self.log("[OK] Extraction completed successfully. Ready for Optimization.")
                    self.optimize_btn.setEnabled(True)
                else:
                    self.log(f"[ERROR] File not found: {extracted_file_path}")
                    self.optimize_btn.setEnabled(False)

            except Exception as e:
                self.log(f"[ERROR] Error loading file: {_sanitize_error(e)}")
                self.optimize_btn.setEnabled(False)
        else:
            self.extract_status_label.setText("Erro!")
            self.log(f"[ERROR] Extraction failed: {message}")
            self.optimize_btn.setEnabled(False)
            QMessageBox.critical(self, "Erro", f"Extraction failed:\n\n{message}")

    def on_fast_extract_finished(self, results: dict):
        """Callback quando ULTIMATE EXTRACTION SUITE V 9.5 PRO termina."""
        self.extract_status_label.setText("Concluído!")
        self.extract_progress_bar.setValue(100)

        try:
            # Pega caminho do arquivo gerado
            output_file = results.get('output_file')

            if output_file and os.path.exists(output_file):
                self.extracted_file = output_file
                self.trans_file_label.setText(os.path.basename(output_file))
                self.trans_file_label.setStyleSheet("color: #FF9800; font-weight: bold;")

                # Log estatísticas V7.0
                valid_strings = results.get('valid_strings', 0)
                recovered_strings = results.get('recovered_strings', 0)
                total_strings = results.get('total_strings', valid_strings + recovered_strings)
                approval_rate = results.get('approval_rate', 0)
                pattern_engine_used = results.get('pattern_engine_used', False)

                self.log(f"[OK] NEUROROM AI V 7.0 PRO SUITE: Extração concluída!")
                self.log(f"[STATS] Strings principais: {valid_strings}")
                if recovered_strings > 0:
                    self.log(f"🔍 Strings recuperadas: {recovered_strings}")
                self.log(f"🎉 Total extraído: {total_strings}")
                self.log(f"📈 Taxa de aprovação: {approval_rate:.1f}%")
                if pattern_engine_used:
                    self.log(f"🔬 Pattern Engine ativado - tabela detectada!")
                self.log(f"📂 Arquivo salvo: {os.path.basename(output_file)}")

                # Habilita otimização (opcional neste caso, pois já está filtrado)
                self.optimize_btn.setEnabled(True)

                # Mostra mensagem de sucesso
                msg = f"NEUROROM AI V 7.0 PRO SUITE: Extração concluída com sucesso!\n\n"
                msg += f"Strings principais: {valid_strings}\n"
                if recovered_strings > 0:
                    msg += f"Strings recuperadas: {recovered_strings}\n"
                msg += f"Total: {total_strings}\n"
                msg += f"Taxa de aprovação: {approval_rate:.1f}%\n\n"
                msg += f"Arquivo: {os.path.basename(output_file)}"

                QMessageBox.information(self, "Sucesso", msg)
            else:
                self.log(f"[ERROR] Arquivo não encontrado: {output_file}")
                self.optimize_btn.setEnabled(False)

        except Exception as e:
            self.log(f"[ERROR] Erro ao processar resultado: {_sanitize_error(e)}")
            self.optimize_btn.setEnabled(False)

    def on_fast_extract_error(self, error_msg: str):
        """Callback quando ocorre erro na extração."""
        self.extract_status_label.setText("Erro!")
        self.log(f"[ERROR] Erro na extração: {error_msg}")
        self.optimize_btn.setEnabled(False)
        QMessageBox.critical(self, "Erro", f"Falha na extração:\n\n{error_msg}")

    def translate_texts(self):
        input_file = self.optimized_file
        input_lower = str(input_file or "").lower()
        jsonl_mode = bool(input_lower.endswith(".jsonl"))

        if not input_file or not os.path.exists(input_file):
            QMessageBox.warning(self, "Aviso", "Select an optimized file first!")
            return

        if jsonl_mode and not self._confirm_advanced_jsonl_translation(input_file):
            return

        self._realtime_filter_technical_noise = bool(jsonl_mode)
        if jsonl_mode:
            self.log(
                "🧩 Modo avançado: JSONL direto selecionado. "
                "Fluxo padrão recomendado: safe/optimized TXT."
            )

        mode_index = self.mode_combo.currentIndex()
        mode_text = self.mode_combo.currentText()

        # Verifica se modo requer API key (Gemini e ChatGPT precisam)
        needs_api_key = mode_index in [0, 2]  # Gemini ou ChatGPT

        if needs_api_key:
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                if mode_index == 0:
                    QMessageBox.warning(self, "Aviso", "API Key do Google Gemini é necessária!\n\nObtenha em: aistudio.google.com/apikey")
                else:
                    QMessageBox.warning(self, "Aviso", "API Key da OpenAI é necessária!\n\nObtenha em: platform.openai.com/api-keys")
                return
        else:
            api_key = ""

        self.translate_btn.setEnabled(False)
        self.stop_translation_btn.setEnabled(True)  # Habilita botão PARAR
        self.translation_progress_bar.setValue(0)
        self.translation_status_label.setText("Starting Worker...")

        target_lang_name = self.target_lang_combo.currentText()

        # Escolhe Worker baseado no modo
        if mode_index == 0:  # Gemini (Google AI)
            self.log(f"⚡ Gemini (Google AI): {os.path.basename(input_file)}...")
            self.translate_thread = GeminiWorker(api_key, input_file, target_lang_name)
        elif mode_index == 1:  # Llama (Ollama Local)
            self.log(f"🦙 Llama (Ollama Local): {os.path.basename(input_file)}...")
            self.translate_thread = OllamaWorker(input_file, target_lang_name)
        elif mode_index == 2:  # ChatGPT (OpenAI)
            self.log(f"🤖 ChatGPT (OpenAI): {os.path.basename(input_file)}...")
            self.translate_thread = ChatGPTWorker(api_key, input_file, target_lang_name)
        else:
            QMessageBox.information(self, "Info", f"Modo '{mode_text}' não implementado!")
            self.translate_btn.setEnabled(True)
            self.stop_translation_btn.setEnabled(False)
            return

        self.translate_thread.progress_signal.connect(self.translation_progress_bar.setValue)
        self.translate_thread.status_signal.connect(self.translation_status_label.setText)
        self.translate_thread.log_signal.connect(self.log)
        self.translate_thread.finished_signal.connect(self.on_gemini_finished)
        self.translate_thread.error_signal.connect(self.on_gemini_error)
        self.translate_thread.realtime_signal.connect(self.update_realtime_panel)
        self.translate_thread.start()

    def stop_translation(self):
        """Para a tradução em andamento"""
        if hasattr(self, 'translate_thread') and self.translate_thread and self.translate_thread.isRunning():
            reply = QMessageBox.question(
                self,
                'Confirmar',
                '[WARN] Tem certeza que deseja PARAR a tradução?\n\nO progresso até agora será salvo.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.log("🛑 Parando tradução...")
                self.translate_thread.stop()  # Chama método stop() do worker
                self.translate_thread.wait()  # Aguarda thread terminar
                self.translation_status_label.setText("[ERROR] Parado pelo usuário")
                self.translate_btn.setEnabled(True)
                self.stop_translation_btn.setEnabled(False)
                self.log("[OK] Tradução parada. Progresso parcial foi salvo.")

    def on_gemini_finished(self, output_file: str):
        self.translation_progress_bar.setValue(100)
        self.translation_status_label.setText("Concluído!")
        self.log(f"Translation saved: {os.path.basename(output_file)}")

        self.translated_file = output_file
        qa_target = self.translated_file or output_file
        if (
            qa_target
            and str(qa_target).lower().endswith(".jsonl")
            and run_qa_gate is not None
        ):
            try:
                p = Path(qa_target)
                pure_candidates = [
                    p.with_name(p.name.replace("_translated.jsonl", "_pure_text.jsonl")),
                    p.with_name(p.name.replace(".jsonl", "_pure_text.jsonl")),
                    p.parent.parent / "1_extracao" / p.name.replace("_translated.jsonl", "_pure_text.jsonl"),
                ]
                pure_jsonl = None
                for cand in pure_candidates:
                    if cand.exists() and cand.is_file():
                        pure_jsonl = str(cand)
                        break
                if pure_jsonl:
                    mapping_json = None
                    pure_path = Path(pure_jsonl)
                    map_cand = pure_path.with_name(
                        pure_path.name.replace("_pure_text.jsonl", "_reinsertion_mapping.json")
                    )
                    if map_cand.exists() and map_cand.is_file():
                        mapping_json = str(map_cand)
                    if run_autoretry_for_translation is not None:
                        qa_res = run_autoretry_for_translation(
                            pure_jsonl_path=pure_jsonl,
                            translated_jsonl_path=str(p),
                            mapping_json_path=mapping_json,
                            max_retries=max(
                                1,
                                min(
                                    10,
                                    int(os.environ.get("NEUROROM_AUTORETRY_MAX", "3") or "3"),
                                ),
                            ),
                        )
                        qa_obj = qa_res.get("qa_gate", {}) if isinstance(qa_res, dict) else {}
                        self.log(
                            "[QA_GATE] tradução: "
                            f"pass={str(bool(qa_obj.get('pass', False))).lower()} "
                            f"attempts={qa_res.get('attempts', 1)} "
                            f"repairs={qa_res.get('repairs', 0)} "
                            f"changed={str(bool(qa_res.get('changed', False))).lower()} "
                            f"failed={json.dumps(qa_obj.get('failed_checks', []), ensure_ascii=False)}"
                        )
                    else:
                        qa_obj = run_qa_gate(
                            pure_jsonl_path=pure_jsonl,
                            translated_jsonl_path=str(p),
                            mapping_json_path=mapping_json,
                            stage="post_translation",
                        )
                        self.log(
                            "[QA_GATE] tradução: "
                            f"pass={str(bool(qa_obj.get('pass', False))).lower()} "
                            f"failed={json.dumps(qa_obj.get('failed_checks', []), ensure_ascii=False)}"
                        )
            except Exception as qa_err:
                self.log(f"[WARN] QA_GATE pós-tradução falhou: {_sanitize_error(qa_err)}")

        self.translated_file_label.setText(Path(output_file).name)
        self.translated_file_label.setStyleSheet("color:#2196F3;font-weight:bold;")

        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        self.tabs.setTabEnabled(2, True)
        QMessageBox.information(self, self.tr("congratulations_title"), self.tr("congratulations_message"))

    def on_gemini_error(self, error_msg: str):
        self.translation_status_label.setText("Erro Fatal")
        self.log(f"Translation error: {error_msg}")
        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        QMessageBox.critical(self, "Erro", f"Translation error:\n{error_msg}")

    def _looks_like_technical_noise_for_realtime(self, text: str) -> bool:
        t = str(text or "").strip()
        if not t:
            return True
        if re.fullmatch(r"(?:0x)?[0-9A-Fa-f]{6,}", t):
            return True
        if re.fullmatch(r"[A-Za-z0-9]{5,16}", t):
            vowels = sum(1 for c in t.lower() if c in "aeiouáéíóúãõâêôà")
            if vowels <= 1:
                return True
            if (
                any(c.islower() for c in t)
                and any(c.isupper() for c in t)
                and not re.search(r"[a-z]{3,}", t)
            ):
                return True
        return False

    def _should_skip_realtime_entry(self, original: str, translated: str) -> bool:
        if not bool(getattr(self, "_realtime_filter_technical_noise", False)):
            return False
        return (
            self._looks_like_technical_noise_for_realtime(original)
            and self._looks_like_technical_noise_for_realtime(translated)
        )

    def update_realtime_panel(self, original: str, translated: str, translator: str):
        """Atualiza painel de tradução em tempo real"""
        if self._should_skip_realtime_entry(original, translated):
            return
        # Trunca textos longos para caber no painel
        max_len = 80
        orig_display = original[:max_len] + "..." if len(original) > max_len else original
        trans_display = translated[:max_len] + "..." if len(translated) > max_len else translated

        self.realtime_original_label.setText(f"Original: {orig_display}")
        self.realtime_translated_label.setText(f"Tradução: {trans_display}")
        self.realtime_info_label.setText(f"⚡ Tradutor: {translator}")

    def restart_application(self):
        self.log("Reiniciando aplicação...")
        self.save_config()
        self.cleanup_threads()

        python = sys.executable
        script = sys.argv[0]
        if sys.platform == 'win32':
            subprocess.Popen([python, script], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([python, script])
        QApplication.quit()

    def cleanup_threads(self):
        """Encerra threads com segurança antes de sair."""
        if self.extract_thread and self.extract_thread.isRunning():
            self.extract_thread.terminate()
            self.extract_thread.wait()

        if self.optimize_thread and self.optimize_thread.isRunning():
            self.optimize_thread.stop()
            self.optimize_thread.quit()
            self.optimize_thread.wait(1000)
            if self.optimize_thread.isRunning():
                self.optimize_thread.terminate()

        if self.translate_thread and self.translate_thread.isRunning():
            self.translate_thread.stop()
            self.translate_thread.quit()
            self.translate_thread.wait(1000)
            if self.translate_thread.isRunning():
                self.translate_thread.terminate()

        if self.reinsert_thread and self.reinsert_thread.isRunning():
            self.reinsert_thread.requestInterruption()
            self.reinsert_thread.quit()
            self.reinsert_thread.wait(1000)
            if self.reinsert_thread.isRunning():
                self.reinsert_thread.terminate()
    def log(self, message: str):
        """Versão LIMPA e CORRIGIDA para o programa abrir."""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Verifica se o painel de log existe
            if hasattr(self, 'log_text') and self.log_text is not None:
                self.log_text.append(f"[{timestamp}] {message}")
                from PyQt6.QtGui import QTextCursor
                self.log_text.moveCursor(QTextCursor.MoveOperation.End)
            else:
                # Fallback para o terminal se a interface ainda não carregou
                print(f"[{timestamp}] {message}")
        except Exception as e:
            print(f"Erro no log: {_sanitize_error(e)} | Msg: {message}")

    def log_message(self, message: str):
        """Função centralizada para enviar mensagens para o log de operações da aba gráfica."""
        timestamp = datetime.now().strftime("[%H:%M:%S]")

        # Se estamos na aba gráfica, usa o log específico dela
        if hasattr(self, 'gfx_log_text'):
            self.gfx_log_text.append(f"{timestamp} {message}")
            scrollbar = self.gfx_log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        # Senão, usa o log principal
        elif hasattr(self, 'log_text'):
            self.log_text.append(f"{timestamp} {message}")
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def load_config(self):
        if ProjectConfig.CONFIG_FILE.exists():
            try:
                with open(ProjectConfig.CONFIG_FILE, 'r') as f:
                    config = json.load(f)

                    if 'theme' in config:
                        self.current_theme = config['theme']
                        # Set combo with translated theme name
                        translated_name = self.get_translated_theme_name(self.current_theme)
                        self.theme_combo.setCurrentText(translated_name)
                        ThemeManager.apply(QApplication.instance(), self.current_theme)

                    if 'ui_lang' in config:
                        self.current_ui_lang = config['ui_lang']
                        for name, code in ProjectConfig.UI_LANGUAGES.items():
                            if code == self.current_ui_lang:
                                self.ui_lang_combo.setCurrentText(name)
                                break
                        self.refresh_ui_labels()

                    if 'font_family' in config:
                        self.current_font_family = config['font_family']
                        self.font_combo.setCurrentText(self.current_font_family)
                        self.change_font_family(self.current_font_family)

                    if 'workers' in config:
                        self.workers_spin.setValue(config['workers'])

                    if 'timeout' in config:
                        self.timeout_spin.setValue(config['timeout'])

                    self.log("Configuração carregada")
            except Exception as e:
                self.log(f"Falha ao carregar configuração: {_sanitize_error(e)}")

    def save_config(self):
        config = {
            'theme': self.current_theme,
            'ui_lang': self.current_ui_lang,
            'font_family': self.current_font_family,
            'api_key_obfuscated': _obfuscate_key(self.api_key_edit.text()),
            'workers': self.workers_spin.value(),
            'timeout': self.timeout_spin.value(),
            'last_saved': datetime.now().isoformat()
        }
        try:
            with open(ProjectConfig.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Falha ao salvar configuração: {_sanitize_error(e)}")

    def on_source_language_changed(self, language_name: str):
        """Update source language when user changes selection."""
        # Find corresponding language code
        for name, code in ProjectConfig.SOURCE_LANGUAGES.items():
            if name == language_name:
                self.source_language_code = code
                self.source_language_name = name
                self.log(f"[LANG] Source language: {name} ({code})")
                break

    def on_target_language_changed(self, language_name: str):
        """Update target language when user changes selection."""
        # Find corresponding language code
        for name, code in ProjectConfig.TARGET_LANGUAGES.items():
            if name == language_name:
                self.target_language_code = code
                self.target_language_name = name
                if hasattr(self, "output_rom_edit") and self.output_rom_edit is not None:
                    if getattr(self, "original_rom_path", None):
                        file_basename = Path(self.original_rom_path).stem
                        file_ext = Path(self.original_rom_path).suffix or ".ext"
                        self.output_rom_edit.setPlaceholderText(
                            self._build_output_placeholder_text(file_basename, file_ext)
                        )
                    else:
                        self.output_rom_edit.setPlaceholderText(
                            self._build_output_placeholder_text()
                        )
                self.log(f"[LANG] Target language: {name} ({code})")
                break

    def show_manual_step(self, index: int):
        """COMMERCIAL GRADE: Display manual instructions in professional popup."""
        if index == 0:
            return

        self.manual_combo.setCurrentIndex(0)

        if index == 3:
            self.show_step3_help()
            return

        # Handle Graphics Guide (index 5)
        if index == 5:
            self.show_graphics_guide()
            return

        # Handle PC Games Guide (index 6)
        if index == 6:
            self.show_pc_games_guide()
            return

        step_title_keys = [
            "manual_step_1_title",
            "manual_step_2_title",
            "manual_step_3_title",
            "manual_step_4_title"
        ]

        step_content_keys = [
            "manual_step_1_content",
            "manual_step_2_content",
            "manual_step_3_content",
            "manual_step_4_content"
        ]

        step_title = self.tr(step_title_keys[index - 1])
        step_content = self.tr(step_content_keys[index - 1])

        dialog = QDialog(self)
        dialog.setWindowTitle(step_title)
        dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        content_label = QLabel(step_content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        # COMMERCIAL GRADE: Set consistent font size for all content
        dialog_font = QFont("Segoe UI", 11)  # Unified 11pt font
        content_label.setFont(dialog_font)
        content_layout.addWidget(content_label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_graphics_guide(self):
        """Exibe o manual com tradução dinâmica baseada no idioma selecionado."""
        dialog = QDialog(self)

        # TÍTULO TRADUZIDO DINAMICAMENTE
        self.setWindowTitle("NeuroROM AI - Universal Localization Suite v7.0 [PRO ELITE]")
        dialog.setMinimumSize(700, 600)

        # FORÇA O TEMA ESCURO (Corrige a tela branca)
        dialog.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3e3e3e;
                padding: 15px;
                font-size: 14px;
            }
            h2 { color: #4da6ff; }
            h3 { color: #ffcc00; margin-top: 20px; }
            li { margin-bottom: 5px; }
            QPushButton {
                background-color: #007acc; color: white; border: none;
                padding: 10px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0098ff; }
        """)

        layout = QVBoxLayout(dialog)

        # TEXTO DO MANUAL TRADUZIDO DINAMICAMENTE (Busca do JSON do idioma atual)
        text_area = QTextEdit()
        text_area.setHtml(self.tr("manual_gfx_body"))
        text_area.setReadOnly(True)
        layout.addWidget(text_area)

        # BOTÃO FECHAR TRADUZIDO DINAMICAMENTE
        btn_close = QPushButton(self.tr("btn_close_manual"))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def show_pc_games_guide(self):
        """Exibe o guia de tradução de jogos de PC."""
        dialog = QDialog(self)

        # TÍTULO TRADUZIDO DINAMICAMENTE
        dialog.setWindowTitle(self.tr("manual_pc_games_title"))
        dialog.setMinimumSize(800, 700)

        # FORÇA O TEMA ESCURO
        dialog.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3e3e3e;
                padding: 15px;
                font-size: 14px;
            }
            h2 { color: #4da6ff; }
            h3 { color: #ffcc00; margin-top: 20px; }
            li { margin-bottom: 5px; }
            QPushButton {
                background-color: #007acc; color: white; border: none;
                padding: 10px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0098ff; }
        """)

        layout = QVBoxLayout(dialog)

        # TEXTO DO MANUAL TRADUZIDO DINAMICAMENTE
        text_area = QTextEdit()
        text_area.setHtml(self.tr("manual_pc_games_body"))
        text_area.setReadOnly(True)
        layout.addWidget(text_area)

        # BOTÃO FECHAR TRADUZIDO DINAMICAMENTE
        btn_close = QPushButton(self.tr("btn_close_manual"))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _create_emoji_text_widget(self, emoji: str, text: str, bold: bool = False) -> QWidget:
        """COMMERCIAL GRADE: Create widget with separated emoji and text for consistent sizing."""
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Emoji label with fixed large size
        emoji_label = QLabel(emoji)
        emoji_font = QFont("Segoe UI Emoji", 20)  # Fixed large size for emojis
        emoji_label.setFont(emoji_font)
        h_layout.addWidget(emoji_label)

        # Text label with normal size
        text_label = QLabel(f"<b>{text}</b>" if bold else text)
        text_label.setTextFormat(Qt.TextFormat.RichText if bold else Qt.TextFormat.PlainText)
        text_font = QFont("Segoe UI", 11)  # Normal text size
        text_label.setFont(text_font)
        text_label.setWordWrap(True)
        h_layout.addWidget(text_label, 1)  # Stretch text label

        return container

    def show_step3_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("help_step3_title"))
        dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # COMMERCIAL GRADE: Separated emoji/text for consistent sizing
        text_font = QFont("Segoe UI", 11)

        # Objective - Extract emoji from translation
        obj_title_text = self.tr('help_step3_objective_title')
        obj_title = self._create_emoji_text_widget("🎯", obj_title_text.replace("🎯", "").strip(), bold=True)
        content_layout.addWidget(obj_title)

        obj_text = QLabel(self.tr("help_step3_objective_text"))
        obj_text.setWordWrap(True)
        obj_text.setFont(text_font)
        content_layout.addWidget(obj_text)
        content_layout.addSpacing(10)

        # Instructions
        inst_title_text = self.tr('help_step3_instructions_title')
        inst_title = self._create_emoji_text_widget("📝", inst_title_text.replace("📝", "").strip(), bold=True)
        content_layout.addWidget(inst_title)

        inst_text = QLabel(self.tr("help_step3_instructions_text"))
        inst_text.setWordWrap(True)
        inst_text.setFont(text_font)
        content_layout.addWidget(inst_text)
        content_layout.addSpacing(10)

        # Expectations
        expect_title_text = self.tr('help_step3_expect_title')
        expect_title = self._create_emoji_text_widget("[OK]", expect_title_text.replace("[OK]", "").strip(), bold=True)
        content_layout.addWidget(expect_title)

        expect_text = QLabel(self.tr("help_step3_expect_text"))
        expect_text.setWordWrap(True)
        expect_text.setFont(text_font)
        content_layout.addWidget(expect_text)
        content_layout.addSpacing(10)

        # Auto Mode
        auto_title_text = self.tr('help_step3_automode_title')
        auto_title = self._create_emoji_text_widget("[START]", auto_title_text.replace("[START]", "").strip(), bold=True)
        content_layout.addWidget(auto_title)

        auto_text = QLabel(self.tr("help_step3_automode_text"))
        auto_text.setWordWrap(True)
        auto_text.setFont(text_font)
        content_layout.addWidget(auto_text)
        content_layout.addSpacing(10)

        # Estilos de Localização
        style_title = self._create_emoji_text_widget("🎨", "Estilos de Localização", bold=True)
        content_layout.addWidget(style_title)

        style_text = QLabel(self.tr("help_step3_style_text"))
        style_text.setWordWrap(True)
        style_text.setFont(text_font)
        content_layout.addWidget(style_text)
        content_layout.addSpacing(10)

        # Gêneros de Jogo
        genre_title = self._create_emoji_text_widget("🎮", "Gêneros de Jogo", bold=True)
        content_layout.addWidget(genre_title)

        genre_text = QLabel(self.tr("help_step3_genre_text"))
        genre_text.setWordWrap(True)
        genre_text.setFont(text_font)
        content_layout.addWidget(genre_text)
        content_layout.addSpacing(10)

        # Painel de Tradução em Tempo Real
        realtime_title = self._create_emoji_text_widget("📺", "Painel de Tradução em Tempo Real", bold=True)
        content_layout.addWidget(realtime_title)

        realtime_text = QLabel(self.tr("help_step3_realtime_text"))
        realtime_text.setWordWrap(True)
        realtime_text.setFont(text_font)
        content_layout.addWidget(realtime_text)
        content_layout.addSpacing(10)

        # Cache de Traduções
        cache_title = self._create_emoji_text_widget("💾", "Cache de Traduções", bold=True)
        content_layout.addWidget(cache_title)

        cache_text = QLabel(self.tr("help_step3_cache_text"))
        cache_text.setWordWrap(True)
        cache_text.setFont(text_font)
        content_layout.addWidget(cache_text)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def load_config(self):
        """Load saved configuration from JSON file."""
        if not ProjectConfig.CONFIG_FILE.exists():
            return

        try:
            with open(ProjectConfig.CONFIG_FILE, 'r') as f:
                config = json.load(f)

            # Restore theme
            theme_name = config.get('theme', 'Preto (Black)')
            if theme_name in ProjectConfig.THEMES:
                self.current_theme = theme_name
                if hasattr(self, 'theme_combo'):
                    # Set combo with translated theme name
                    translated_name = self.get_translated_theme_name(theme_name)
                    self.theme_combo.setCurrentText(translated_name)
                self.change_theme(translated_name)

            # Restore UI language
            ui_lang_code = config.get('ui_lang', 'en')
            self.current_ui_lang = ui_lang_code
            for lang_name, code in ProjectConfig.UI_LANGUAGES.items():
                if code == ui_lang_code:
                    if hasattr(self, 'ui_lang_combo'):
                        self.ui_lang_combo.setCurrentText(lang_name)
                    break

            # Restore font family
            font_name = config.get('font_family', 'Padrão (Segoe UI + CJK Fallback)')
            if font_name in ProjectConfig.FONT_FAMILIES:
                self.current_font_family = font_name
                if hasattr(self, 'font_combo'):
                    self.font_combo.setCurrentText(font_name)
                self.change_font_family(font_name)

            # Restore workers and timeout
            if hasattr(self, 'workers_spin'):
                self.workers_spin.setValue(config.get('workers', 4))
            if hasattr(self, 'timeout_spin'):
                self.timeout_spin.setValue(config.get('timeout', 30))

            # CRITICAL FIX: Refresh UI labels after restoring language
            self.refresh_ui_labels()

            self.log("Configuração carregada com sucesso.")

        except Exception as e:
            self.log(f"Falha ao carregar configuração: {_sanitize_error(e)}")

    def save_config(self):
        """Save current configuration to JSON file."""
        def _obfuscate_key(key: str) -> str:
            if not key:
                return ""
            return base64.b64encode(key.encode('utf-8')).decode('utf-8')

        config = {
            'theme': self.current_theme,
            'ui_lang': self.current_ui_lang,
            'font_family': self.current_font_family,
            'api_key_obfuscated': _obfuscate_key(self.api_key_edit.text()),
            'workers': self.workers_spin.value(),
            'timeout': self.timeout_spin.value(),
            'last_saved': datetime.now().isoformat()
        }
        try:
            with open(ProjectConfig.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Falha ao salvar configuração: {_sanitize_error(e)}")

    def closeEvent(self, event):
        self.cleanup_threads()
        self.save_config()
        event.accept()
    def run_forensic_analysis(self):
        """Executa a análise forense (Raio-X) da ROM selecionada."""
        if not self.original_rom_path:
            self.log("[ERROR] Nenhuma ROM selecionada para análise forense.")
            return

        # Cancela análise anterior se ainda estiver rodando
        if self.engine_detection_thread and self.engine_detection_thread.isRunning():
            self.log("[WARN] Análise anterior ainda em andamento, aguarde...")
            return

        self.log("🔍 Iniciando análise forense (Raio-X)...")
        self.forensic_analysis_btn.setEnabled(False)
        self.forensic_progress.setVisible(True)

        # Escolhe o worker de detecção com base na disponibilidade do Tier1
        if USE_TIER1_DETECTION:
            self.engine_detection_thread = EngineDetectionWorkerTier1(self.original_rom_path)
            # Conecta o sinal de progresso específico do Tier1
            self.engine_detection_thread.progress_signal.connect(self.on_engine_detection_progress)
        else:
            self.engine_detection_thread = EngineDetectionWorker(self.original_rom_path)

        # USA O MÉTODO COMPLETO que já existe e funciona perfeitamente
        self.engine_detection_thread.detection_complete.connect(self.on_engine_detection_complete)

        # Conecta finished para limpar a thread
        self.engine_detection_thread.finished.connect(self.on_forensic_thread_finished)

        # Inicia a thread
        self.engine_detection_thread.start()

    def on_forensic_thread_finished(self):
        """Limpeza após conclusão da thread de análise forense."""
        self.forensic_analysis_btn.setEnabled(True)
        self.forensic_progress.setVisible(False)
        self.engine_detection_thread = None

def main():
    # Silenciar avisos de fonte Qt (não críticos)
    os.environ['QT_LOGGING_RULES'] = 'qt.text.font.db=false'

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Define a fonte padrão
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    # Aplica o tema inicial
    ThemeManager.apply(app, "Preto (Black)")

    # Cria e exibe a janela principal
    window = MainWindow()
    window.show()

    # Inicia o loop de eventos (isso mantém a janela aberta)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
