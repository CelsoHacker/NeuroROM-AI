r"""
================================================================================
ROM Translation Framework - Main Interface
================================================================================
Universal ROM Translation Framework
Platforms: SMS (V1)
================================================================================
"""
# pylint: disable=C0301,W0201,C0116,W0718,C0415,R0915,R0914,R0912,W0621,C0103,R1702,R1732,R1705,W0404,C0327,R1724,W0109,C0413,W0108,R0911,C0115,W1514,C0201,C0412,C0302,R0913,R0917,C0200,R0903,R0902,W0105,R0904
# Motivo: arquivo monolítico legado; a limpeza total do lint será tratada em refatorações futuras.

import sys
import os
import json
import subprocess
import re
import shutil
import traceback
import base64
import binascii
import importlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import zlib
import unicodedata

# ================== CONFIGURAÇÃO DO SYS.PATH ==================
# Adicione o diretório raiz do projeto para que os módulos core sejam encontrados
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# Utilitário para dependências opcionais
def _optional_import(module_name: str):
    """Tenta importar módulo opcional sem quebrar a execução."""
    try:
        if importlib.util.find_spec(module_name) is None:
            return None
    except (ModuleNotFoundError, ValueError):
        return None
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _sanitize_error(msg) -> str:
    """Remove possíveis API keys / tokens de mensagens de erro."""
    s = str(msg)
    s = re.sub(r'AIza[0-9A-Za-z\-_]{10,}', '[REDACTED]', s)
    s = re.sub(r'([?&]key=)[^&\s]+', r'\1[REDACTED]', s)
    s = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{10,}', r'\1[REDACTED]', s)
    s = re.sub(r'sk-[A-Za-z0-9]{10,}', 'sk-[REDACTED]', s)
    return s


def _jsonl_has_tilemap_entries(path: str, max_lines: int = 300) -> bool:
    """Detecta se um JSONL contém entradas tilemap seguras para reinserção."""
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                enc = str(obj.get("encoding", "")).lower()
                if enc == "tilemap" and bool(obj.get("reinsertion_safe", False)):
                    return True
    except Exception:
        return False
    return False


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
    from core.engine_detector import EngineDetector, detect_game_engine

    print("[OK]EngineDetector importado com sucesso")
except ImportError as e:
    print(f"[ERROR]Erro ao importar EngineDetector: {_sanitize_error(e)}")

    # Fallback para desenvolvimento
    def detect_game_engine(file_path):
        return {
            "type": "UNKNOWN",
            "platform": "Unknown",
            "engine": "Unknown",
            "notes": "Engine detector não disponível",
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
import collections
from collections import defaultdict

# Optional dependencies with graceful fallbacks
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False
    print("Warning: numpy not available. Some features may be limited.")

sklearn_ensemble = _optional_import("sklearn.ensemble")
joblib = _optional_import("joblib")
RandomForestClassifier = (
    getattr(sklearn_ensemble, "RandomForestClassifier", None)
    if sklearn_ensemble
    else None
)
SKLEARN_AVAILABLE = RandomForestClassifier is not None and joblib is not None
if not SKLEARN_AVAILABLE:
    print("Warning: scikit-learn not available. ML features disabled.")

cv2 = _optional_import("cv2")
CV2_AVAILABLE = cv2 is not None
if not CV2_AVAILABLE:
    print("Warning: opencv not available. Image processing features limited.")

pytesseract = _optional_import("pytesseract")
Image = _optional_import("PIL.Image") if pytesseract else None
TESSERACT_AVAILABLE = pytesseract is not None and Image is not None
if TESSERACT_AVAILABLE:
    # Configure o caminho do Tesseract para Windows
    if sys.platform == "win32":
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print("Warning: pytesseract/PIL not available. OCR features disabled.")

requests = _optional_import("requests")
REQUESTS_AVAILABLE = requests is not None

psutil = _optional_import("psutil")
PSUTIL_AVAILABLE = psutil is not None

# Importações PyQt6 CORRETAS
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QFileDialog,
    QComboBox,
    QProgressBar,
    QGroupBox,
    QGridLayout,
    QTabWidget,
    QToolButton,
    QAbstractItemView,
    QMenu,
    QAbstractButton,
    QMenuBar,
    QAbstractScrollArea,
    QMessageBox,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QFormLayout,
    QDialog,
    QScrollArea,
    QFrame,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsDropShadowEffect,
    QStyle,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    QRectF,
    QTimer,
    QObject,
    QSize,
    QEvent,
    QByteArray,
    QUrl,
)
from PyQt6.QtGui import (
    QFont,
    QFontDatabase,
    QFontInfo,
    QTextCursor,
    QPalette,
    QColor,
    QDesktopServices,
    QPixmap,
    QImage,
    QPainter,
    QIcon,
    QBrush,
    QPen,
    QTransform,
)


def _get_theme_border_color(theme_name: str, window_color: str) -> str:
    """Calcula cor de borda com contraste consistente por tema."""
    if theme_name == "Preto (Black)":
        return "#2E2E2E"
    return "#4A4A4A"

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
    from core.MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL import (
        UniversalMasterSystemExtractor,
    )

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
        analyze_compression_type,
    )

    print("[OK]Forensic Engine Tier 1 importado com sucesso")
    USE_TIER1_DETECTION = True
except ImportError as e1:
    try:
        # Fallback: import direto (se executado da pasta interface)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        from forensic_engine_upgrade import (
            EngineDetectionWorkerTier1,
            FORENSIC_SIGNATURES_TIER1,
            calculate_entropy_shannon,
            estimate_year_from_binary,
            calculate_confidence_score,
            analyze_compression_type,
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
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
            )

            percent_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*%")

            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.progress.emit(line)
                    match = percent_pattern.search(line)
                    if match:
                        try:
                            self.progress_percent.emit(int(float(match.group(1))))
                        except (ValueError, TypeError):
                            pass

            self.process.wait()

            success = self.process.returncode == 0
            if success:
                self.finished.emit(True, "Operation completed successfully")
            else:
                stderr = self.process.stderr.read().strip()
                self.finished.emit(
                    False, f"Error code {self.process.returncode}: {stderr}"
                )
        except Exception as e:
            self.finished.emit(False, f"Exception: {_sanitize_error(e)}")

    def terminate(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.process.kill()
                except OSError:
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
                "preserve_commands": True,
                "replace_symbol": "@",
                "replace_with": " ",
                "remove_overlaps": True,
            }
        self.config = config

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.status_signal.emit("Analisando arquivo...")
            self.progress_signal.emit(10)

            with open(self.input_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_original = len(lines)
            self.log_signal.emit(f"[STATS] Linhas originais: {total_original:,}")
            self.progress_signal.emit(20)

            # FASE 1: LIMPEZA COM PARSING DO FORMATO [0xENDERECO] OU JSONL
            self.status_signal.emit("Parsing formato [0xENDERECO]/JSONL...")
            cleaned_texts = []
            seen_texts = set()  # Apenas para estatística de duplicatas
            suspect_items = []  # Itens marcados como lixo binário (preservados)
            is_jsonl = self.input_file.lower().endswith(".jsonl")

            stats = {
                "comments": 0,
                "no_bracket": 0,
                "too_short": 0,
                "no_vowels": 0,
                "has_code_chars": 0,
                "binary_garbage": 0,  # NOVO: Filtro ultra-rigoroso
                "duplicates": 0,
                "kept": 0,
                "json_errors": 0,
                "invalid_offset": 0,
                "no_text": 0,
            }
            # --- NOVO: Rastreadores para evitar repetições (Ecos) ---
            last_offset = -1
            last_text_len = 0

            def parse_offset_value(value):
                if value is None:
                    return None
                if isinstance(value, int):
                    return value
                if isinstance(value, str):
                    s = value.strip()
                    try:
                        return int(s, 16) if s.lower().startswith("0x") else int(s)
                    except ValueError:
                        return None
                return None

            for i, line in enumerate(lines):
                if not self._is_running:
                    self.error_signal.emit("Operação cancelada pelo usuário")
                    return

                original_line = line.strip()

                # FILTRO 1: IGNORAR COMENTÁRIOS
                if original_line.startswith("#"):
                    stats["comments"] += 1
                    continue

                clean_text = ""
                current_offset = None
                obj = None

                if is_jsonl or original_line.startswith("{"):
                    try:
                        obj = json.loads(original_line)
                    except json.JSONDecodeError:
                        stats["json_errors"] += 1
                        continue

                    current_offset = parse_offset_value(
                        obj.get("offset", obj.get("origin_offset", obj.get("static_offset")))
                    )
                    if current_offset is None:
                        stats["invalid_offset"] += 1
                        continue

                    clean_text = (
                        obj.get("text_src")
                        or obj.get("text")
                        or obj.get("original_text")
                        or obj.get("translated_text")
                        or ""
                    )
                    if not isinstance(clean_text, str) or not clean_text.strip():
                        stats["no_text"] += 1
                        continue
                    clean_text = clean_text.strip()
                else:
                    # FILTRO 2: SEPARAR O LIXO - Pegar só o texto depois do ']'
                    if "]" not in original_line:
                        stats["no_bracket"] += 1
                        continue

                    # Divide no primeiro ']' e pega a parte depois
                    parts = original_line.split("]", 1)
                    if len(parts) < 2:
                        stats["no_bracket"] += 1
                        continue
                    clean_text = parts[1].strip()
                    # 1. PEGA O ENDEREÇO (OFFSET) PARA COMPARAR
                    try:
                        offset_hex = parts[0].replace("[", "").strip()
                        current_offset = int(offset_hex, 16)
                    except (ValueError, TypeError):
                        stats["invalid_offset"] += 1
                        continue

                # 2. [OK] SUBSTITUIÇÃO CONFIGURÁVEL (V 9.5 Expert Mode)
                replace_symbol = self.config.get("replace_symbol", "@")
                replace_with = self.config.get("replace_with", " ")
                if replace_symbol and replace_with is not None:
                    clean_text = clean_text.replace(replace_symbol, replace_with)

                # 3. [OK] FILTRO DE ECO CONFIGURÁVEL (V 9.5 Expert Mode)
                # Se o endereço atual é menor que o fim do texto anterior, é lixo repetido.
                if self.config.get("remove_overlaps", True) and not is_jsonl:
                    if current_offset < (last_offset + last_text_len):
                        stats["duplicates"] += 1
                        continue  # Pula Mushroom/ushroom/shroom

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
                preserve_commands = self.config.get("preserve_commands", True)
                if any(char in clean_text for char in ["{", "}", "\\", "/"]):
                    if self.is_pc_game and not preserve_commands:
                        # Se for PC E preserve_commands=False, colchetes e barras são LIXO técnico. DELETA.
                        stats["has_code_chars"] += 1
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
                if re.search(
                    r"(0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]{2,}|^[0-9A-F]{4,}$|[0-9]{2,}[><@#\-\+][0-9])",
                    clean_text,
                ):
                    stats["binary_garbage"] += 1
                    is_garbage = True

                # 6.2: Padrões hexadecimais com símbolos (!dAdBdC, @ABCD, @ABCD$&H)
                if not is_garbage:
                    # Padrão 1: Símbolos seguidos de letras maiúsculas (ex: @ABCD, #3CCC)
                    if re.search(r"[!@#$%^&*`][A-Z]{2,}", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True
                    # Padrão 2: Letras com símbolos no meio (ex: ABC$&H, 2BBB)
                    elif re.search(r"[A-Z]{2,}[\$&\*\^%#][A-Z&\$\*]", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True
                    # Padrão 3: Números com letras hexadecimais (ex: 2BBB, 3CCC)
                    elif re.search(r"[0-9][A-F]{3,}", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.3: Sequências minúsculas/maiúsculas curtas (4+ letras sem espaço)
                if not is_garbage:
                    # Minúsculas consecutivas: tuvw, ktuwv
                    if re.match(r"^[a-z`]{4,}$", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True
                    # Maiúsculas curtas sem vogais: IJYZ, DCBA, HIXY
                    elif re.match(r"^[A-Z]{4,8}$", clean_text) and not re.search(
                        r"[AEIOU]", clean_text
                    ):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.4: Sequências aleatórias (gibberish) - padrões caóticos
                if not is_garbage and len(clean_text) >= 4:
                    # Padrões como: eHV(Wb, V:FGiks, JjJ)@I@
                    if re.search(
                        r"[A-Z][a-z][A-Z]\(|[A-Z]:[A-Z]|[A-Z][a-z][A-Z]\)", clean_text
                    ):
                        stats["binary_garbage"] += 1
                        is_garbage = True
                    # Muitas alternâncias maiúsc/minúsc: AaBbCc, JjJI
                    elif (
                        sum(
                            1
                            for i in range(len(clean_text) - 1)
                            if clean_text[i].isupper() != clean_text[i + 1].isupper()
                        )
                        > len(clean_text) * 0.6
                    ):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.5: Caracteres especiais excessivos (>=30% RIGOROSO)
                if not is_garbage:
                    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\")
                    special_count = sum(
                        1 for char in clean_text if char in special_chars
                    )
                    if len(clean_text) > 0 and special_count / len(clean_text) >= 0.30:
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.6: Repetição excessiva (< 30% caracteres únicos - mais permissivo)
                if not is_garbage and len(clean_text) > 5:
                    unique_chars = len(set(clean_text))
                    if unique_chars < len(clean_text) * 0.3:
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.7: Sequências com números misturados (07>37O4, 61-64+6E)
                if not is_garbage and len(clean_text) >= 6:
                    # Conta transições número→letra→número
                    num_letter_transitions = sum(
                        1
                        for i in range(len(clean_text) - 2)
                        if clean_text[i].isdigit()
                        and clean_text[i + 1].isalpha()
                        and clean_text[i + 2].isdigit()
                    )
                    if num_letter_transitions >= 2:
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.8: Sequências longas sem espaços e sem palavras reais (>15 chars)
                if not is_garbage and len(clean_text) > 15 and " " not in clean_text:
                    # Se não tem espaço E não tem palavras comuns = provável lixo
                    stats["binary_garbage"] += 1
                    is_garbage = True

                # 6.9: Ratio de vogais/consoantes muito baixo (texto sem vogais suficientes)
                if not is_garbage and len(clean_text) >= 4:
                    vowel_count = sum(1 for c in clean_text if c.lower() in "aeiou")
                    consonant_count = sum(
                        1
                        for c in clean_text
                        if c.isalpha() and c.lower() not in "aeiou"
                    )
                    # RIGOROSO: ratio < 0.40 para strings curtas (4-8 chars)
                    if consonant_count > 0 and vowel_count > 0:
                        vowel_ratio = vowel_count / consonant_count
                        # Strings curtas precisam de mais vogais
                        if len(clean_text) <= 8 and vowel_ratio < 0.40:
                            stats["binary_garbage"] += 1
                            is_garbage = True
                        # Strings longas podem ter ratio menor
                        elif len(clean_text) > 8 and vowel_ratio < 0.25:
                            stats["binary_garbage"] += 1
                            is_garbage = True

                # 6.10: Caracteres repetidos consecutivos (JJJJ, AAAA, 8888, etc.)
                if not is_garbage:
                    # 4+ caracteres iguais consecutivos = lixo
                    if re.search(r"(.)\1{3,}", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.11: Começar com símbolos especiais, números ou caracteres suspeitos
                if not is_garbage:
                    # Linhas que começam com @#$%^&*`0-9 geralmente são lixo
                    if re.match(r"^[@#$%^&*`0-9\[\]\(\)]", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.12: Strings curtas/médias (4-15 chars) com caracteres especiais OU números
                if not is_garbage and 4 <= len(clean_text) <= 15:
                    # Se tiver caracteres especiais OU números em string curta/média, provável lixo
                    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789")
                    if any(c in special_chars for c in clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.13: Padrões de tiles/gráficos (mix de maiúsc/minúsc sem sentido)
                if not is_garbage and len(clean_text) >= 5:
                    # Detecta padrões como: "iPCP", "bcBA", "den]", "nmh]O="
                    lower_count = sum(1 for c in clean_text if c.islower())
                    upper_count = sum(1 for c in clean_text if c.isupper())
                    # Se tiver mix balanceado de maiúsc/minúsc E tiver símbolos = lixo
                    if lower_count > 0 and upper_count > 0:
                        if abs(lower_count - upper_count) <= 2:  # Balanceado
                            special_chars = set(
                                "!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\0123456789"
                            )
                            if any(c in special_chars for c in clean_text):
                                stats["binary_garbage"] += 1
                                is_garbage = True

                # 6.14: Sequências com números no meio (XO5678OX, uu5678uu5678)
                if not is_garbage and len(clean_text) >= 6:
                    # Se tiver 3+ dígitos consecutivos no meio de letras = lixo
                    if re.search(r"[A-Za-z]+[0-9]{3,}[A-Za-z]+", clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.15: Repetições de padrões de 2-3 caracteres (IJIJIJ, quququ)
                if not is_garbage and len(clean_text) >= 6:
                    # Detecta padrões como: XYXYXY, quququ
                    for pattern_len in [2, 3]:
                        for i in range(len(clean_text) - pattern_len * 2):
                            pattern = clean_text[i : i + pattern_len]
                            # Verifica se o padrão se repete imediatamente
                            next_part = clean_text[
                                i + pattern_len : i + pattern_len * 2
                            ]
                            if pattern == next_part and pattern.isalpha():
                                stats["binary_garbage"] += 1
                                is_garbage = True
                                break
                        if is_garbage:
                            break

                # 6.16: Strings curtas (<8 chars) com mix maiúsc/minúsc SEM espaços
                if (
                    not is_garbage
                    and 4 <= len(clean_text) < 8
                    and " " not in clean_text
                ):
                    lower_count = sum(1 for c in clean_text if c.islower())
                    upper_count = sum(1 for c in clean_text if c.isupper())
                    # Se tiver ambos (mix) = provável lixo (iPCP, bcBA, JLjlEE)
                    if lower_count >= 1 and upper_count >= 1:
                        # Exceção: se for tudo letra (sem números/símbolos) e tiver padrão de palavra
                        if not clean_text.isalpha():
                            stats["binary_garbage"] += 1
                            is_garbage = True

                # 6.17: Strings que terminam com símbolos estranhos
                if not is_garbage:
                    # Termina com símbolos como: ", ], ), etc. (exceto . ! ?)
                    if re.search(r'["\]\)\|`]$', clean_text):
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.18: Relaxado (não filtra mix maiúsc/minúsc em strings curtas)

                # 6.19: Strings MAIÚSCULAS (4-12 chars) com letras repetidas consecutivas (padrão de lixo)
                if (
                    not is_garbage
                    and 4 <= len(clean_text) <= 12
                    and clean_text.isupper()
                ):
                    # Detecta padrões: NNLVVU, IIHFHH, EKKH, AAAQQQ, VVUUVW, etc.
                    # Se tiver 2+ pares de letras duplicadas = lixo
                    duplicate_pairs = sum(
                        1
                        for i in range(len(clean_text) - 1)
                        if clean_text[i] == clean_text[i + 1]
                    )
                    if duplicate_pairs >= 2:
                        stats["binary_garbage"] += 1
                        is_garbage = True

                # 6.20: Relaxado (não filtra consoantes raras)

                # EXCEÇÕES: Palavras de jogos são SEMPRE válidas
                game_words = [
                    "mario",
                    "world",
                    "super",
                    "player",
                    "start",
                    "pause",
                    "game",
                    "over",
                    "score",
                    "time",
                    "level",
                    "stage",
                    "lives",
                    "coin",
                    "press",
                    "continue",
                    "menu",
                    "option",
                    "sound",
                    "music",
                    "jump",
                    "run",
                    "fire",
                    "bonus",
                    "yoshi",
                    "power",
                    "star",
                    "shell",
                    "switch",
                    "button",
                    "special",
                    "secret",
                    "enemy",
                    "boss",
                    "castle",
                    "exit",
                    "save",
                    "load",
                    "reset",
                    "friend",
                    "rescue",
                    "princess",
                    "bowser",
                    "luigi",
                    "peach",
                    "trapped",
                    "help",
                    "blocks",
                    "complete",
                    "explore",
                    "different",
                    "places",
                    "defeat",
                    "points",
                    "stomp",
                    "pressing",
                    "jumping",
                    "fence",
                    "pool",
                    "balance",
                    "further",
                    "between",
                    "left",
                    "right",
                    "down",
                    "pick",
                    "towards",
                    "spin",
                    "break",
                ]

                # Regra extra: Se tiver qualquer uma das palavras acima, SALVA.
                if any(word in clean_text.lower() for word in game_words):
                    is_garbage = False

                # === CORREÇÃO DE EMERGÊNCIA PARA SUPER MARIO WORLD ===
                # 1. Se for texto curto (2 ou 3 letras) e alfanumérico (UP, ON, x99), SALVA.
                if (
                    len(clean_text) >= 2
                    and len(clean_text) <= 3
                    and clean_text.replace(" ", "").isalnum()
                ):
                    is_garbage = False

                # 2. Se for tudo MAIÚSCULO (Menus do SNES), SALVA.
                if clean_text.isupper():
                    is_garbage = False
                # =====================================================

                # Regra extra: se for apenas letras, não considera lixo binário
                if clean_text.isalpha():
                    is_garbage = False

                # [OK] FILTRO DE LIXO BINÁRIO ATIVADO (20 sub-filtros rigorosos)
                # Se detectado como lixo pelos 20 filtros acima, marca como suspeito (NÃO descarta em JSONL)
                if is_garbage:
                    if is_jsonl:
                        suspect_items.append(
                            {
                                "offset_hex": f"0x{current_offset:06X}"
                                if current_offset is not None
                                else None,
                                "byte_len": (
                                    obj.get("max_len_bytes")
                                    if isinstance(obj, dict)
                                    else None
                                )
                                or (obj.get("max_len") if isinstance(obj, dict) else None)
                                or (
                                    len(clean_text.encode("utf-8", errors="ignore"))
                                    if clean_text
                                    else 0
                                ),
                                "terminator": obj.get("terminator")
                                if isinstance(obj, dict)
                                else None,
                                "raw_bytes_hex": (
                                    obj.get("raw_bytes_hex")
                                    if isinstance(obj, dict)
                                    else ""
                                )
                                or (
                                    obj.get("bytes_hex") if isinstance(obj, dict) else ""
                                )
                                or (
                                    obj.get("raw_hex") if isinstance(obj, dict) else ""
                                )
                                or "",
                                "text_attempt": clean_text,
                                "confidence": "low",
                                "reason_flags": ["binary_junk"],
                            }
                        )
                    else:
                        continue

                # FILTRO 7: DUPLICATAS
                clean_text_lower = clean_text.lower()
                if clean_text_lower in seen_texts:
                    stats["duplicates"] += 1
                else:
                    seen_texts.add(clean_text_lower)

                # APROVADO! Adiciona apenas o texto limpo
                cleaned_texts.append(clean_text)
                stats["kept"] += 1

                # Atualização de progresso
                if i % 1000 == 0:
                    progress = 20 + int((i / total_original) * 60)
                    self.progress_signal.emit(progress)

            self.progress_signal.emit(80)
            self.status_signal.emit("Salvando arquivo otimizado...")

            # Salvar arquivo otimizado (SEM os prefixos [0x...])
            output_file = self.input_file.replace(
                "_extracted_texts.txt", "_optimized.txt"
            )
            if output_file == self.input_file:
                output_file = (
                    str(Path(self.input_file).with_suffix("")) + "_optimized.txt"
                )

            with open(output_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(cleaned_texts))

            # Exporta suspeitos (lixo binário) sem afetar JSONL/MAPPING/PROOF
            suspect_path = None
            if is_jsonl and suspect_items:
                try:
                    out_dir = Path(self.input_file).parent
                    file_name = Path(self.input_file).name
                    match = re.search(r"([0-9A-Fa-f]{8})", file_name)
                    crc_tag = match.group(1).upper() if match else "UNKNOWN"
                    suspect_path = out_dir / f"{crc_tag}_suspect_text.jsonl"

                    with open(
                        suspect_path, "w", encoding="utf-8", newline="\n"
                    ) as f:
                        for entry in suspect_items:
                            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                    # Atualiza report.txt com offsets suspeitos
                    report_path = out_dir / f"{crc_tag}_report.txt"
                    offsets = [
                        item.get("offset_hex")
                        for item in suspect_items
                        if item.get("offset_hex")
                    ]
                    report_lines = [
                        "",
                        "[WARN] SUSPECT_TEXTS (binary_junk) - PRESERVADOS",
                        f"TOTAL={len(suspect_items)}",
                    ]
                    if offsets:
                        report_lines.append("OFFSETS=" + ", ".join(offsets))
                    report_lines.append("")

                    if report_path.exists():
                        with open(report_path, "a", encoding="utf-8") as f:
                            f.write("\n".join(report_lines))
                    else:
                        with open(report_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(report_lines))
                except Exception:
                    # Não quebra a otimização se falhar export de suspeitos
                    pass

            total_removed = total_original - stats["kept"]

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
            self.log_signal.emit(
                f"  • Caracteres de código ({{}}\\/) : {stats['has_code_chars']:,}"
            )
            if is_jsonl:
                self.log_signal.emit(
                    f"  [INFO] Lixo binário (hex/gibberish/tiles) detectado (preservado): {stats['binary_garbage']:,}"
                )
                self.log_signal.emit(
                    f"  • Duplicatas detectadas (preservadas): {stats['duplicates']:,}"
                )
            else:
                self.log_signal.emit(
                    f"  [INFO] Lixo binário (hex/gibberish/tiles): {stats['binary_garbage']:,}"
                )
                self.log_signal.emit(f"  • Duplicatas: {stats['duplicates']:,}")
            self.log_signal.emit(f"  • JSON inválido: {stats['json_errors']:,}")
            self.log_signal.emit(f"  • Offset inválido: {stats['invalid_offset']:,}")
            self.log_signal.emit(f"  • Sem texto: {stats['no_text']:,}")
            self.log_signal.emit("")
            self.log_signal.emit("💾 Arquivo salvo (SOMENTE TEXTOS LIMPOS).")
            if suspect_path is not None:
                self.log_signal.emit("🧾 Suspeitos salvos.")
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
            core_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"
            )
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
            self.progress_signal.emit(
                "[START] Iniciando ULTIMATE EXTRACTION SUITE V7.0..."
            )

            with redirect_stdout(output_buffer):
                results = extractor.extract_all()

            # Emite progresso
            output = output_buffer.getvalue()
            for line in output.split("\n"):
                if line.strip():
                    self.progress_signal.emit(line)

            self.progress_percent_signal.emit(100)
            self.finished_signal.emit(results)

        except Exception as e:
            self.error_signal.emit(f"Erro na extração: {_sanitize_error(e)}")


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

    def __init__(
        self,
        api_key: str,
        input_file: str,
        target_language: str = "Portuguese (Brazil)",
    ):
        super().__init__()
        self.api_key = api_key
        self.input_file = input_file
        self.target_language = target_language
        self._is_running = True
        self._fallback_warned = False
        self._translated_ok = 0  # Contador de linhas realmente traduzidas

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
        protected = text
        tag_counter = len(self.protected_tags)

        # PADRÃO 1: Tags com chaves {PLAYER}, {NAME}, etc.
        pattern_braces = r"\{[A-Z_]+\}"
        for match in re.finditer(pattern_braces, text):
            tag = match.group(0)
            placeholder = f"{self.placeholder_prefix}{tag_counter}__"
            self.protected_tags.append((tag, placeholder))
            protected = protected.replace(tag, placeholder, 1)
            tag_counter += 1

        # PADRÃO 2: Tags com colchetes [WAIT], [END], [COLOR:RED], etc.
        pattern_brackets = r"\[[\w:]+\]"
        for match in re.finditer(pattern_brackets, text):
            tag = match.group(0)
            placeholder = f"{self.placeholder_prefix}{tag_counter}__"
            self.protected_tags.append((tag, placeholder))
            protected = protected.replace(tag, placeholder, 1)
            tag_counter += 1

        # PADRÃO 3: Escape sequences \\s, \\n, \\t
        pattern_escapes = r"\\[snt]"
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
        """Worker thread para tradução com Gemini - COM VALIDAÇÃO E LOGS DETALHADOS"""
        try:
            import time as _time
            from collections import deque as _deque
            _start_time = _time.time()
            _recent_timestamps = _deque(maxlen=20)  # Últimos 20 itens para taxa móvel

            # 0. LOG INICIAL PARA DEBUG
            self.log_signal.emit("[DEBUG] GeminiWorker.run() iniciado")

            # 1. Verifica disponibilidade da biblioteca
            if not gemini_api or not gemini_api.GENAI_AVAILABLE:
                self.error_signal.emit(
                    "Biblioteca 'google-generativeai' não instalada.\n"
                    "Execute: pip install google-generativeai"
                )
                return

            # 1.5 PRÉ-VALIDAÇÃO DA API KEY (antes de iniciar tradução)
            self.log_signal.emit("[INFO] Validando API Key...")
            self.log_signal.emit(f"[INFO] API key: [REDACTED] (len={len(self.api_key)})")

            try:
                is_valid, validation_msg = gemini_api.test_api_key(self.api_key)
                validation_msg = _sanitize_error(validation_msg) if validation_msg else validation_msg
                if not is_valid:
                    # Distingue erro de modelo não encontrado vs API key inválida
                    if (
                        "modelo" in validation_msg.lower()
                        or "model" in validation_msg.lower()
                    ):
                        self.error_signal.emit(f"[ERROR] {validation_msg}")
                    else:
                        self.error_signal.emit(
                            f"[ERROR] API Key inválida: {validation_msg}"
                        )
                    self.log_signal.emit(
                        f"[ERROR] Falha na validação: {validation_msg}"
                    )
                    return
                self.log_signal.emit("[OK] API Key validada com sucesso!")
            except Exception as val_err:
                safe_err = _sanitize_error(val_err)
                self.error_signal.emit(
                    f"[ERROR] Erro ao validar API Key: {safe_err}"
                )
                self.log_signal.emit(f"[ERROR] Exceção na validação: {safe_err}")
                return

            # 2. Abre o arquivo
            with open(self.input_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = (
                    str(Path(self.input_file).with_suffix("")) + "_translated.txt"
                )

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
                    partes = line_protected.split("]", 1)
                    texto_original = (
                        partes[1].strip() if len(partes) > 1 else line_protected
                    )
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
                            current_batch, self.api_key, self.target_language, 120.0
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
                                    self._translated_ok += 1
                        else:
                            self.log_signal.emit(f"[WARN] Erro na API: {error_msg}")
                            # Se a API falhar, mantém o original para não perder o arquivo
                            for orig in batch_original_lines:
                                translated_lines.append(orig + "\n")

                        # Atualiza a interface com ETA por taxa móvel
                        _recent_timestamps.append(_time.time())
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        remaining = total_lines - (i + 1)
                        if len(_recent_timestamps) >= 2:
                            window = _recent_timestamps[-1] - _recent_timestamps[0]
                            rate_items_min = (
                                (len(_recent_timestamps) - 1) / (window / 60.0)
                                if window > 0 else 0
                            )
                            eta_min = (
                                remaining / rate_items_min
                                if rate_items_min > 0 else 0
                            )
                            self.status_signal.emit(
                                f"Traduzindo... {percent}% | "
                                f"ETA: {eta_min:.1f}min | "
                                f"{rate_items_min:.0f} items/min"
                            )
                        else:
                            self.status_signal.emit(f"Traduzindo... {percent}%")

                        # Limpa os lotes para a próxima rodada
                        current_batch = []
                        batch_original_lines = []

                    except Exception as e:
                        self.log_signal.emit(
                            f"[ERROR] Erro no processamento do lote: {_sanitize_error(e)}"
                        )
                        for orig in batch_original_lines:
                            translated_lines.append(orig + "\n")
                        current_batch = []
                        batch_original_lines = []

            # 5. Salva o arquivo final
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(translated_lines)

            if self._translated_ok > 0:
                self.finished_signal.emit(output_file)
            else:
                self.error_signal.emit(
                    "Nenhuma linha foi traduzida. Verifique sua API key ou o limite diário."
                )

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

    def __init__(
        self,
        api_key: str,
        input_file: str,
        target_language: str = "Portuguese (Brazil)",
    ):
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

            with open(self.input_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)
            translated_lines = []
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = (
                    str(Path(self.input_file).with_suffix("")) + "_translated.txt"
                )

            self.log_signal.emit(
                f"🤖 AUTO Mode: {total_lines} linhas (Gemini primeiro, Ollama se quota esgotar)"
            )

            # Auto-start Ollama se não estiver rodando (fallback precisa estar pronto)
            import requests as _req
            try:
                _req.get("http://127.0.0.1:11434/api/tags", timeout=2)
            except Exception:
                self.log_signal.emit("[START] Iniciando Ollama automaticamente (fallback)...")
                try:
                    import subprocess as _sp
                    if sys.platform == "win32":
                        _sp.Popen(["ollama", "serve"], creationflags=0x08000000,
                                  stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                    else:
                        _sp.Popen(["ollama", "serve"], stdout=_sp.DEVNULL,
                                  stderr=_sp.DEVNULL, start_new_session=True)
                    for _wait in range(15):
                        time.sleep(1)
                        try:
                            _req.get("http://127.0.0.1:11434/api/tags", timeout=2)
                            self.log_signal.emit("[OK] Ollama pronto para fallback!")
                            break
                        except Exception:
                            self.log_signal.emit(f"⏳ Iniciando Ollama... {_wait+1}/15s")
                except FileNotFoundError:
                    self.log_signal.emit("[WARN] Ollama não instalado - fallback indisponível")
                except Exception:
                    self.log_signal.emit("[WARN] Não foi possível iniciar Ollama automaticamente")

            # Cria tradutor híbrido
            translator = HybridTranslator(api_key=self.api_key, prefer_gemini=True)

            self.log_signal.emit(
                f"[OK] Gemini: {'Disponível' if translator.gemini_available else 'Indisponível'}"
            )
            self.log_signal.emit(
                f"[OK] Ollama: {'Disponível' if translator.ollama_available else 'Indisponível'}"
            )

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
                            current_batch, self.target_language, TranslationMode.AUTO
                        )

                        # Mostra status atual
                        stats = translator.get_stats()

                        if success:
                            translated_lines.extend(translations)
                            # Emite sinal em tempo real (última tradução do lote)
                            if current_batch and translations:
                                last_orig = current_batch[-1] if current_batch else ""
                                last_trans = (
                                    translations[-1].strip() if translations else ""
                                )
                                current_translator = (
                                    "Gemini"
                                    if stats.get("gemini_requests", 0)
                                    >= stats.get("ollama_requests", 0)
                                    else "Ollama"
                                )
                                self.realtime_signal.emit(
                                    last_orig, last_trans, current_translator
                                )
                        else:
                            self.log_signal.emit(f"[WARN] {error_msg}")
                            translated_lines.extend([l + "\n" for l in current_batch])

                        if stats["fallback_switches"] > 0 and not hasattr(
                            self, "_fallback_warned"
                        ):
                            self.log_signal.emit(
                                "🔄 Mudou para Ollama (quota Gemini esgotada)"
                            )
                            self._fallback_warned = True  # Só avisa 1 vez

                        # Atualiza progresso
                        percent = int(((i + 1) / total_lines) * 100)
                        self.progress_signal.emit(percent)
                        self.status_signal.emit(
                            f"{translator.get_status_message()} - {percent}%"
                        )

                        current_batch = []

                    except Exception as e:
                        self.log_signal.emit(f"[ERROR] Erro no lote: {_sanitize_error(e)}")
                        translated_lines.extend([l + "\n" for l in current_batch])
                        current_batch = []

            # Salva arquivo
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(translated_lines)

            # Mostra estatísticas finais
            final_stats = translator.get_stats()
            self.log_signal.emit("\n" + "=" * 50)
            self.log_signal.emit("[STATS] ESTATÍSTICAS FINAIS:")
            self.log_signal.emit(
                f"   Gemini: {final_stats['gemini_requests']} requisições"
            )
            self.log_signal.emit(
                f"   Ollama: {final_stats['ollama_requests']} requisições"
            )
            self.log_signal.emit(f"   Fallbacks: {final_stats['fallback_switches']}")
            self.log_signal.emit(
                f"   Total traduzido: {final_stats['total_texts_translated']} textos"
            )
            self.log_signal.emit("=" * 50)

            self.finished_signal.emit(output_file)

        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Detalhes do Erro: {error_details}")
            self.error_signal.emit(_sanitize_error(e))


class TilemapWorker(QThread):
    """
    Worker dedicado para tradução de JSONL tilemap (SMS/tiles).
    - Tradução direta do *_pure_text.jsonl
    - Ajuste automático de tamanho para evitar cortes
    """

    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    realtime_signal = pyqtSignal(str, str, str)  # original, traduzido, tradutor

    def __init__(
        self,
        input_file: str,
        target_language: str = "Portuguese (Brazil)",
        api_key: str = "",
        prefer_gemini: bool = False,
        model: str = "llama3.1:8b",
    ):
        super().__init__()
        self.input_file = input_file
        self.target_language = target_language
        self.api_key = api_key or ""
        self.prefer_gemini = prefer_gemini
        self.model = model
        self._is_running = True

        # Tokens protegidos
        self._code_prefix = "__CODE"
        self._space_prefix = "__SP"
        # Traduções curtas (menus/linhas pequenas)
        self._short_map = {
            "PRACTICE": "TREINO",
            "NORMAL": "NORMAL",
            "GAME OVER": "FIM DE JOGO",
            "CONTINUE": "CONTINUAR",
            "NEW GAME": "NOVO JOGO",
            "GOOD JOB": "MUITO BEM",
            "YOU SAVED MINNIE FROM": "VOCE SALVOU MINNIE DA",
            "THE EVIL WITCH": "BRUXA MALIGNA",
            "NOW TEST YOUR SKILLS": "AGORA TESTE SUAS HABIL.",
            "WITH THE NORMAL OPTION.": "COM A OPCAO NORMAL.",
            "THERE ARE MANY NEW AND": "HA MUITOS NOVOS E",
            "EXCITING LEVELS AHEAD": "NIVEIS INCRIVEIS",
            "PAUSE": "PAUSA",
            "HI,": "HI,",
        }
        # Traduções compactas para créditos (mantém colunas)
        self._credits_map = {
            "STARRING": "ELENCO",
            "STAFF": "EQUIPE",
            "CHARACTER DESIGN": "DESIGN PERS.",
            "GAME DESIGN": "DESIGN JOGO",
            "SOUND DIRECTOR": "DIRET. SOM",
            "SOUND PROGRAMMER": "PROG. SOM",
            "SOUND COMPOSER": "COMP. SOM",
            "PROGRAMMER": "PROG.",
            "ASSISTANT PROGRAMMERS": "ASSIST. PROG.",
            "PRODUCER": "PROD.",
            "PLANNER": "PLANEJ.",
            "SPECIAL THANKS TO": "AGRADEC.",
            "THANK YOU FOR": "OBRIGADO POR",
            "PLAYING.": "JOGAR.",
        }
        self._crc_tag = self._extract_crc_from_filename(self.input_file)
        self._postfix_rules = self._load_postfix_rules()
        self._short_words = {
            "A", "O", "OS", "AS", "DE", "DO", "DA", "DOS", "DAS",
            "E", "EM", "NO", "NA", "NOS", "NAS", "UM", "UMA", "UNS", "UMAS",
            "POR", "PARA", "COM", "SEM", "AO", "AOS", "À", "ÀS",
        }

    def stop(self):
        self._is_running = False

    def _protect_codes(self, text: str) -> tuple[str, dict]:
        """Protege códigos como {VAR}, [NAME], <0A>."""
        codes = {}
        pattern = r"(\{[^}]+\}|\[[^\]]+\]|<[^>]+>)"

        def _repl(match):
            token = f"{self._code_prefix}{len(codes)}__"
            codes[token] = match.group(0)
            return token

        return re.sub(pattern, _repl, text), codes

    def _protect_spaces(self, text: str) -> tuple[str, dict]:
        """Preserva sequências de espaços para manter layout."""
        spaces = {}

        def _repl(match):
            token = f"{self._space_prefix}{len(spaces)}__"
            spaces[token] = match.group(0)
            return token

        return re.sub(r" {2,}", _repl, text), spaces

    def _restore_tokens(self, text: str, tokens: dict) -> str:
        restored = text
        for token, original in tokens.items():
            restored = restored.replace(token, original)
        return restored

    def _extract_crc_from_filename(self, path: str) -> str | None:
        if not path:
            return None
        m = re.search(r"([0-9A-Fa-f]{8})", os.path.basename(path))
        return m.group(1).upper() if m else None

    def _load_postfix_rules(self) -> list[dict]:
        """Carrega regras de correção por CRC32 (postfix_rules_{CRC32}.json)."""
        crc = self._crc_tag or self._extract_crc_from_filename(self.input_file)
        if not crc:
            return []
        candidates = [
            os.path.join(os.path.dirname(self.input_file), f"postfix_rules_{crc}.json"),
            os.path.join(project_root, "rules", f"postfix_rules_{crc}.json"),
        ]
        rules = []
        for cand in candidates:
            if not os.path.exists(cand):
                continue
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "rules" in data and isinstance(data["rules"], list):
                    rules = data["rules"]
                elif isinstance(data, dict):
                    for k, v in data.items():
                        rules.append({"pattern": str(k), "repl": str(v), "flags": "i"})
                elif isinstance(data, list):
                    rules = data
                break
            except Exception:
                continue
        return rules or []

    def _apply_postfix_rules(self, text: str) -> str:
        if not text or not self._postfix_rules:
            return text
        out = text
        for rule in self._postfix_rules:
            try:
                pattern = rule.get("pattern", "")
                repl = rule.get("repl", "")
                flags = rule.get("flags", "")
                re_flags = re.IGNORECASE if "i" in flags.lower() else 0
                if pattern:
                    out = re.sub(pattern, repl, out, flags=re_flags)
            except Exception:
                continue
        return out

    def _sanitize_tilemap(self, text: str) -> str:
        """Normaliza para o charset do tilemap (sem acentos, uppercase)."""
        cleaned, _ = self._sanitize_tilemap_with_fallback(text)
        return cleaned

    def _sanitize_tilemap_with_fallback(self, text: str) -> tuple[str, int]:
        """Normaliza para charset tilemap e conta fallback."""
        if not text:
            return "", 0
        norm = unicodedata.normalize("NFD", text)
        norm = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
        norm = norm.upper().replace("\r", "").replace("\n", " ")
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?:;'-/()")
        out = []
        fallback = 0
        for ch in norm:
            if ch == " " or ch in allowed:
                out.append(ch)
            else:
                if ch.strip():
                    fallback += 1
                out.append(" ")
        return "".join(out), fallback

    def _infer_tilemap_width(self, text: str, max_chars: int) -> int:
        """Heurística para inferir largura do tilemap (evita cortar palavras)."""
        if max_chars <= 0:
            return 0
        if max_chars <= 30:
            return max_chars

        best_width = min(max_chars, 35)
        best_score = -1e9
        best_trailing = -1.0
        punct = set(".!?,;:")

        max_w = min(40, max_chars)
        for w in range(12, max_w + 1):
            if w <= 0:
                continue
            lines = [text[i:i + w] for i in range(0, len(text), w)]
            if len(lines) < 2:
                continue

            good = 0
            bad = 0
            trailing = 0
            for i, ln in enumerate(lines[:-1]):
                trailing += len(ln) - len(ln.rstrip(" "))
                end = ln[-1]
                nextc = text[(i + 1) * w] if (i + 1) * w < len(text) else ""
                if end == " " or end in punct or nextc == " ":
                    good += 1
                if end.isalnum() and nextc.isalnum():
                    bad += 1

            total = max(1, len(lines) - 1)
            good_ratio = good / total
            bad_ratio = bad / total
            avg_trailing = trailing / total

            score = good_ratio - (bad_ratio * 2.0) + min(0.3, avg_trailing / max(1, w))
            if (score > best_score) or (abs(score - best_score) < 1e-6 and avg_trailing > best_trailing):
                best_score = score
                best_trailing = avg_trailing
                best_width = w

        return max(1, min(best_width, max_chars))

    def _chunk_lines(self, text: str, width: int) -> list[str]:
        if width <= 0:
            return [text]
        lines = [text[i:i + width] for i in range(0, len(text), width)]
        if lines and len(lines[-1]) < width:
            lines[-1] = lines[-1].ljust(width)
        return lines

    def _build_layout_fingerprint(self, lines: list[str], width: int) -> dict:
        """Deriva fingerprint do layout original."""
        line_count = len(lines)
        line_lengths = [len(ln) for ln in lines]
        left_padding = [len(ln) - len(ln.lstrip(" ")) for ln in lines]
        right_padding = [len(ln) - len(ln.rstrip(" ")) for ln in lines]
        has_columns = any(re.search(r"\S {2,}\S", ln) for ln in lines)
        center_votes = 0
        pad_samples = 0
        for lp, rp, ln in zip(left_padding, right_padding, lines):
            if ln.strip():
                pad_samples += 1
                if abs(lp - rp) <= 1 and lp > 0:
                    center_votes += 1
        if has_columns:
            alignment_mode = "COLUMNS"
        elif pad_samples > 0 and center_votes >= max(1, pad_samples // 2):
            alignment_mode = "CENTER"
        else:
            alignment_mode = "LEFT"

        column_signature = []
        for ln in lines:
            runs = [len(m.group(0)) for m in re.finditer(r" {2,}", ln)]
            column_signature.append(runs)

        return {
            "line_count_original": line_count,
            "max_line_len_original": max(line_lengths) if line_lengths else 0,
            "max_line_len_by_line": line_lengths,
            "left_padding": left_padding,
            "column_signature": column_signature,
            "alignment_mode": alignment_mode,
            "width_inferred": width,
        }

    def _min_left_pad(self, lines: list[str]) -> int:
        pads = []
        for ln in lines:
            if ln.strip():
                pads.append(len(ln) - len(ln.lstrip(" ")))
        return min(pads) if pads else 0

    def _wrap_to_lines(self, text: str, width: int, num_lines: int, left_pad: int = 0) -> list[str] | None:
        if width <= 0 or num_lines <= 0:
            return None
        avail = max(1, width - left_pad)
        words = [w for w in text.split(" ") if w]
        lines = []
        cur = ""
        for w in words:
            if not cur:
                if len(w) > avail:
                    return None
                cur = w
            elif len(cur) + 1 + len(w) <= avail:
                cur = f"{cur} {w}"
            else:
                lines.append(cur)
                if len(w) > avail:
                    return None
                cur = w
                if len(lines) >= num_lines:
                    return None
        if len(lines) < num_lines:
            lines.append(cur)
        # pad/truncate
        out = []
        for ln in lines[:num_lines]:
            ln = ln[:avail]
            out.append((" " * left_pad + ln).ljust(width)[:width])
        while len(out) < num_lines:
            out.append(" " * width)
        if len(out) > num_lines:
            return None
        # Se ainda sobraram palavras, overflow
        if len(lines) > num_lines:
            return None
        return out[:num_lines]

    def _wrap_to_lines_variable(self, text: str, width: int, pads: list[int], mask: list[bool]) -> list[str] | None:
        """Quebra texto usando largura e padding por linha (preserva alinhamento original)."""
        if width <= 0 or not pads:
            return None
        words = [w for w in text.split(" ") if w]
        out = []
        for i, pad in enumerate(pads):
            # Linha vazia no original: preserva
            if i < len(mask) and not mask[i]:
                out.append(" " * width)
                continue

            avail = max(1, width - pad)
            cur = ""
            while words:
                w = words[0]
                if not cur:
                    if len(w) > avail:
                        return None
                    cur = w
                    words.pop(0)
                    continue
                if len(cur) + 1 + len(w) <= avail:
                    cur = f"{cur} {w}"
                    words.pop(0)
                else:
                    break

            line = (" " * pad + cur).ljust(width)[:width]
            out.append(line)

        # completa se faltar
        while len(out) < len(pads):
            out.append(" " * width)
        # Se ainda sobrou palavra, overflow
        if words:
            return None
        return out[: len(pads)]

    def _translate_short_phrase(self, text: str) -> str:
        key = re.sub(r"\s+", " ", text.strip().upper())
        if not key:
            return ""
        return self._short_map.get(key, text)

    def _translate_credits_line(self, line: str, width: int) -> str:
        """Traduz linha de créditos preservando colunas (2+ espaços)."""
        if not line.strip():
            return " " * width
        parts = re.split(r"( {2,})", line)
        out = []
        for part in parts:
            if part.startswith(" "):
                out.append(part)
                continue
            seg = part.strip()
            if not seg:
                out.append(part)
                continue
            seg_up = seg.upper()
            seg_tr = self._credits_map.get(seg_up, seg_up)
            seg_tr = self._sanitize_tilemap(seg_tr)
            # Ajusta ao tamanho original do segmento
            if len(seg_tr) > len(part):
                seg_tr = seg_tr[:len(part)]
            out.append(seg_tr.ljust(len(part)))
        line_out = "".join(out)
        return line_out[:width].ljust(width)

    def _trim_to_max(self, text: str, max_chars: int) -> str:
        """Corta sem estourar o limite, priorizando borda de palavra."""
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        cut = text.rfind(" ", 0, max_chars)
        if cut >= int(max_chars * 0.6):
            return text[:cut].rstrip()
        return text[:max_chars].rstrip()

    def _shorten_phrase(self, text: str, max_chars: int) -> str | None:
        """Encurta sem cortar palavras; remove palavras curtas se necessário."""
        if max_chars <= 0:
            return None
        words = [w for w in text.split() if w]
        if not words:
            return None
        joined = " ".join(words)
        if len(joined) <= max_chars:
            return joined
        # Remove palavras curtas primeiro
        filtered = [w for w in words if w.upper() not in self._short_words]
        if filtered:
            joined2 = " ".join(filtered)
            if len(joined2) <= max_chars:
                return joined2
        # Fallback: adiciona até caber
        out = ""
        for w in words:
            if not out:
                if len(w) > max_chars:
                    return None
                out = w
                continue
            if len(out) + 1 + len(w) <= max_chars:
                out = f"{out} {w}"
            else:
                break
        return out if out else None

    def _translate_with_gemini(self, text: str) -> str:
        if not gemini_api or not gemini_api.GENAI_AVAILABLE:
            return text
        translations, success, error_msg = gemini_api.translate_batch(
            [text], self.api_key, self.target_language, 120.0
        )
        if not success or not translations:
            if error_msg:
                self.log_signal.emit(f"[WARN] Gemini: {error_msg}")
            return text
        return str(translations[0]).strip()

    def _translate_with_ollama(self, text: str, max_chars: int) -> str:
        if not REQUESTS_AVAILABLE:
            return text
        limit_line = (
            f"- Limite máximo: {max_chars} caracteres.\n" if max_chars > 0 else ""
        )
        prompt = (
            "Você é um tradutor profissional. Traduza para português brasileiro.\n"
            f"{limit_line}"
            "- Não explique.\n"
            "- Não adicione texto extra.\n"
            "- Não use aspas.\n"
            "- Não altere tokens no formato __SPN__ ou __CODEN__.\n"
            "- Responda SOMENTE com a tradução.\n\n"
            f"{text}"
        )
        try:
            resp = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 512,
                        "num_ctx": 2048,
                    },
                },
                timeout=180,
            )
            if resp.status_code != 200:
                return text
            out = resp.json().get("response", "").strip()
            if out.startswith(("\"", "“")) and out.endswith(("\"", "”")):
                out = out[1:-1].strip()
            return out
        except Exception:
            return text

    def _translate_text(self, text: str, max_chars: int) -> tuple[str, str]:
        """Traduz um texto e retorna (tradução, engine)."""
        if self.prefer_gemini and self.api_key:
            return self._translate_with_gemini(text), "Gemini"
        return self._translate_with_ollama(text, max_chars), "Ollama"

    def _translate_chunked(self, text: str, max_chars: int, chunk_size: int = 200) -> tuple[str, str]:
        """Traduz texto longo em blocos menores para evitar timeout."""
        if len(text) <= chunk_size:
            return self._translate_text(text, max_chars)

        # Prioriza chunk por sentença para reduzir repetições
        sentences = re.split(r"(?<=[.!?])\\s+", text)
        if len(sentences) <= 1:
            sentences = text.split()

        chunks = []
        cur = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            add = s if cur == "" else f"{cur} {s}"
            if len(add) <= chunk_size:
                cur = add
            else:
                if cur:
                    chunks.append(cur)
                cur = s
        if cur:
            chunks.append(cur)

        out = []
        engine = "Ollama"
        for ch in chunks:
            translated, engine = self._translate_text(ch, max_chars)
            out.append(translated.strip())

        merged = " ".join(out).strip()
        # Remove repetições consecutivas simples
        parts = re.split(r"(?<=[.!?])\\s+", merged)
        dedup = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if not dedup or p != dedup[-1]:
                dedup.append(p)
        return " ".join(dedup).strip(), engine

    def _post_fix_text(self, text: str) -> str:
        """Correções rápidas por CRC (postfix_rules_{CRC32}.json)."""
        return self._apply_postfix_rules(text)

    def run(self):
        try:
            if not self.input_file or not os.path.exists(self.input_file):
                self.error_signal.emit("Arquivo JSONL não encontrado.")
                return

            # Carrega entradas tilemap
            entries = []
            with open(self.input_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    enc = str(obj.get("encoding", "")).lower()
                    if enc != "tilemap" or not obj.get("reinsertion_safe", False):
                        continue
                    text = obj.get("text_src") or obj.get("text") or ""
                    if not isinstance(text, str) or not text.strip():
                        continue
                    entries.append(obj)

            if not entries:
                self.error_signal.emit("Nenhum texto tilemap válido encontrado.")
                return

            total = len(entries)
            self.log_signal.emit(f"[CFG] input_path={self.input_file} lines_count={total}")
            self.log_signal.emit(
                f"🧩 Tilemap: {total} textos | Tradução direta via JSONL"
            )

            # Define saída
            output_file = self.input_file
            if output_file.endswith("_pure_text.jsonl"):
                output_file = output_file.replace("_pure_text.jsonl", "_translated.jsonl")
            elif output_file.endswith(".jsonl"):
                output_file = output_file.replace(".jsonl", "_translated.jsonl")
            else:
                output_file = output_file + "_translated.jsonl"

            translated_out = []
            for i, obj in enumerate(entries):
                if not self._is_running:
                    self.log_signal.emit("[WARN] Tradução interrompida pelo usuário.")
                    break

                text_src = obj.get("text_src") or obj.get("text") or ""
                max_len_bytes = int(obj.get("max_len_bytes") or obj.get("max_len") or 0)
                max_chars = max_len_bytes // 2 if max_len_bytes else 0
                source_tag = str(obj.get("source", "")).lower()

                width = self._infer_tilemap_width(text_src, max_chars)
                lines_src = self._chunk_lines(text_src, width) if width else [text_src]
                total_lines = len(lines_src)
                layout_fp = self._build_layout_fingerprint(lines_src, width)
                alignment_mode = layout_fp.get("alignment_mode", "LEFT")
                needs_review = False
                fallback_count = 0

                # Modo colunas (créditos/colunas detectadas)
                if alignment_mode == "COLUMNS":
                    out_lines = [self._translate_credits_line(ln, width) for ln in lines_src]
                    sanitized = "".join(out_lines)
                    engine = "FIXED"
                # Modo centralizado
                elif alignment_mode == "CENTER":
                    plain = " ".join([ln.strip() for ln in lines_src if ln.strip()])
                    plain = re.sub(r"\\s+", " ", plain).strip()
                    safe_text, codes = self._protect_codes(plain.lower())
                    translated, engine = self._translate_chunked(safe_text, max_chars, chunk_size=180)
                    translated = self._restore_tokens(translated, codes)
                    translated = self._post_fix_text(translated)
                    translated, fallback_count = self._sanitize_tilemap_with_fallback(translated)
                    wrapped = self._wrap_to_lines(translated, width, total_lines, left_pad=0)
                    if wrapped is None:
                        short_txt = self._shorten_phrase(translated, width * total_lines)
                        if short_txt:
                            wrapped = self._wrap_to_lines(short_txt, width, total_lines, left_pad=0)
                    if wrapped is None:
                        needs_review = True
                        sanitized = "".join(lines_src)
                    else:
                        out_lines = [ln.center(width) for ln in wrapped]
                        sanitized = "".join(out_lines)
                # Modo curto: usa dicionário (menus e linhas pequenas)
                elif "menu" in source_tag or max_chars <= 30:
                    out_lines = []
                    for ln in lines_src:
                        if not ln.strip():
                            out_lines.append(" " * width)
                            continue
                        left_pad = len(ln) - len(ln.lstrip(" "))
                        seg = ln.strip()
                        trans = self._translate_short_phrase(seg)
                        trans, fb = self._sanitize_tilemap_with_fallback(trans)
                        fallback_count += fb
                        avail = max(1, width - left_pad)
                        if len(trans) > avail:
                            short_txt = self._shorten_phrase(trans, avail)
                            if short_txt:
                                trans = short_txt
                            else:
                                needs_review = True
                                trans = seg
                        out_lines.append((" " * left_pad + trans).ljust(width)[:width])
                    sanitized = "".join(out_lines)
                    engine = "FIXED"
                else:
                    # Tradução por blocos (preserva linhas em branco)
                    out_lines = []
                    idx = 0
                    while idx < total_lines:
                        ln = lines_src[idx]
                        if not ln.strip():
                            out_lines.append(" " * width)
                            idx += 1
                            continue
                        # bloco contínuo de linhas não vazias
                        j = idx
                        while j < total_lines and lines_src[j].strip():
                            j += 1
                        block_lines = lines_src[idx:j]
                        pads = [len(bl) - len(bl.lstrip(" ")) for bl in block_lines]
                        mask = [bool(bl.strip()) for bl in block_lines]
                        plain = " ".join([bl.strip() for bl in block_lines if bl.strip()])
                        plain = re.sub(r"\\s+", " ", plain).strip()
                        plain_for_translate = plain.lower()

                        safe_text, codes = self._protect_codes(plain_for_translate)
                        translated, engine = self._translate_chunked(safe_text, max_chars, chunk_size=180)
                        translated = self._restore_tokens(translated, codes)
                        translated = self._post_fix_text(translated)
                        translated, fb = self._sanitize_tilemap_with_fallback(translated)
                        fallback_count += fb

                        wrapped = self._wrap_to_lines_variable(translated, width, pads, mask)
                        if wrapped is None:
                            short_txt = self._shorten_phrase(translated, width * len(pads))
                            if short_txt:
                                wrapped = self._wrap_to_lines_variable(short_txt, width, pads, mask)
                        if wrapped is None:
                            needs_review = True
                            out_lines.extend(block_lines)
                        else:
                            out_lines.extend(wrapped)
                        idx = j

                    sanitized = "".join(out_lines)

                if fallback_count == 0:
                    sanitized, fb = self._sanitize_tilemap_with_fallback(sanitized)
                    fallback_count += fb

                # Garante tamanho final
                if max_chars > 0:
                    if len(sanitized) < max_chars:
                        sanitized = sanitized.ljust(max_chars)
                    elif len(sanitized) > max_chars:
                        extra = len(sanitized) - max_chars
                        if extra > 0 and sanitized[-extra:].strip() == "":
                            sanitized = sanitized[:max_chars]
                        else:
                            needs_review = True
                            fallback_src = "".join(lines_src)
                            fallback_src, _ = self._sanitize_tilemap_with_fallback(fallback_src)
                            sanitized = fallback_src.ljust(max_chars)[:max_chars]

                out_obj = dict(obj)
                out_obj["text_dst"] = sanitized
                out_obj["translated_text"] = sanitized
                out_obj["layout_fingerprint"] = layout_fp
                out_obj["alignment_mode"] = alignment_mode
                out_obj["needs_review"] = bool(needs_review)
                out_obj["charset_fallback_chars"] = int(fallback_count)
                translated_out.append(json.dumps(out_obj, ensure_ascii=False))

                percent = int(((i + 1) / total) * 100)
                self.progress_signal.emit(percent)
                self.status_signal.emit(f"Traduzindo tilemap... {percent}%")
                self.realtime_signal.emit(text_src, sanitized, engine)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(translated_out))

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

    def __init__(
        self,
        input_file: str,
        target_language: str = "Portuguese (Brazil)",
        model: str = "llama3.1:8b",
        style: str = "classic_90s",
        genre: str = "auto",
    ):
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
            if not REQUESTS_AVAILABLE:
                self.error_signal.emit(
                    "Biblioteca 'requests' não instalada. Execute: pip install requests"
                )
                return
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import time

            # Importa módulos de otimização e validação ROM
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from core.translation_optimizer import TranslationOptimizer
            from core.rom_text_validator import ROMTextValidator
            from core.rom_translation_prompts import ROMTranslationPrompts

            # AUTO-START: Verifica e inicia Ollama automaticamente
            ollama_running = False

            try:
                response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    ollama_running = True
                    self.log_signal.emit("[OK] Ollama já está rodando")
            except requests.exceptions.RequestException:
                ollama_running = False

            # Inicia Ollama automaticamente se não estiver rodando
            if not ollama_running:
                self.log_signal.emit("[START] Iniciando Ollama automaticamente...")
                self.status_signal.emit("Iniciando Llama 3.1...")

                try:
                    # Windows: inicia sem janela visível
                    if sys.platform == "win32":
                        CREATE_NO_WINDOW = 0x08000000
                        subprocess.Popen(
                            ["ollama", "serve"],
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        subprocess.Popen(
                            ["ollama", "serve"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True,
                        )

                    # Aguarda inicialização (máx 15 segundos)
                    self.log_signal.emit("⏳ Aguardando Llama 3.1 inicializar...")
                    for i in range(15):
                        time.sleep(1)
                        try:
                            response = requests.get(
                                "http://127.0.0.1:11434/api/tags", timeout=2
                            )
                            if response.status_code == 200:
                                ollama_running = True
                                self.log_signal.emit("[OK] Llama 3.1 pronto!")
                                break
                        except requests.exceptions.RequestException:
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
                    self.error_signal.emit(
                        f"[ERROR] Erro ao iniciar: {_sanitize_error(e)}\n\nAbra CMD e execute: ollama serve"
                    )
                    return

            # [OK] NOVA VALIDAÇÃO: Verifica se modelo específico está instalado
            try:
                models_response = requests.get(
                    "http://127.0.0.1:11434/api/tags", timeout=5
                )
                if models_response.status_code == 200:
                    installed_models = models_response.json().get("models", [])
                    model_names = [m.get("name", "") for m in installed_models]

                    # Verifica se modelo existe (exato ou com variações de tag)
                    model_base = self.model.split(":")[
                        0
                    ]  # Ex: "llama3.2" de "llama3.2:3b"
                    model_found = any(model_base in name for name in model_names)

                    if not model_found:
                        available_models = (
                            ", ".join(model_names[:5]) if model_names else "Nenhum"
                        )
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
                        self.log_signal.emit(
                            f"[OK] Modelo '{self.model}' encontrado e pronto para uso"
                        )
            except Exception as e:
                self.log_signal.emit(
                    f"[WARN] Não foi possível verificar modelos instalados: {_sanitize_error(e)}"
                )
                # Continua mesmo assim (pode ser versão antiga do Ollama)

            # Tenta UTF-8, se falhar usa Latin-1 (aceita todos os bytes)
            try:
                with open(self.input_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines()]
            except UnicodeDecodeError:
                self.log_signal.emit("[WARN] Arquivo não é UTF-8, usando Latin-1...")
                with open(self.input_file, "r", encoding="latin-1") as f:
                    lines = [line.strip() for line in f.readlines()]

            total_lines = len(lines)
            output_file = self.input_file.replace("_optimized.txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = (
                    str(Path(self.input_file).with_suffix("")) + "_translated.txt"
                )

            # === FASE 1: OTIMIZAÇÃO AGRESSIVA PRÉ-TRADUÇÃO ===
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("🔧 FASE 1: OTIMIZAÇÃO AGRESSIVA")
            self.log_signal.emit("=" * 60)

            cache_file = os.path.join(
                os.path.dirname(self.input_file), "translation_cache.json"
            )
            optimizer = TranslationOptimizer(cache_file=cache_file)

            self.log_signal.emit(f"[STATS] Textos originais: {total_lines:,}")
            self.log_signal.emit(
                "🔍 Aplicando filtros: deduplicação, cache, heurísticas..."
            )

            unique_texts, index_mapping = optimizer.optimize_text_list(
                lines,
                skip_technical=True,
                skip_proper_nouns=False,  # Mantenha False para não perder nomes de personagens
                min_entropy=0.30,
                use_cache=True,
            )

            self.log_signal.emit(optimizer.get_stats_report())

            # Se não há nada para traduzir, reconstrói e salva
            if len(unique_texts) == 0:
                self.log_signal.emit("[OK] Todos os textos já em cache ou filtrados!")
                reconstructed = optimizer.reconstruct_translations(
                    [], lines, index_mapping
                )
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(reconstructed))
                self.finished_signal.emit(output_file)
                return

            # === FASE 2: TRADUÇÃO OTIMIZADA ===
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("[START] FASE 2: TRADUÇÃO (SOMENTE TEXTOS ÚNICOS)")
            self.log_signal.emit("=" * 60)

            # DETECÇÃO AUTOMÁTICA DE WORKERS (hardware-aware)
            MAX_WORKERS = self._detect_optimal_workers()  # 1 worker = UI fluida

            # BATCH SIZE otimizado: 8-16 linhas (prompts curtos = mais estável)
            if len(unique_texts) < 1000:
                BATCH_SIZE = 12
            elif len(unique_texts) < 10000:
                BATCH_SIZE = 16
            else:
                BATCH_SIZE = 16

            self.log_signal.emit(
                f"⚡ Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS} (otimizado para UI fluida)"
            )
            self.log_signal.emit(
                "🌡️ Modo de Proteção Térmica Ativo: Adicionando intervalos para resfriamento da GPU"
            )
            estimated_time = (
                len(unique_texts) / BATCH_SIZE / MAX_WORKERS
            ) * 2.0  # Estimativa realista
            self.log_signal.emit(
                f"⏱️  Tempo estimado: ~{estimated_time:.1f} minutos (com respiros térmicos)"
            )

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
                if not text or not isinstance(text, str):
                    return True, "Texto vazio ou inválido"

                text_clean = text.strip()
                if len(text_clean) < 1:
                    return True, "Texto muito curto"

                # ========== EXCEÇÕES: TEXTOS VÁLIDOS DE JOGOS ==========

                # [OK] EXCEÇÃO 1: Palavras comuns de jogos (aceitar SEMPRE)
                common_game_words = {
                    # Inglês
                    "mario",
                    "world",
                    "super",
                    "player",
                    "start",
                    "pause",
                    "game",
                    "over",
                    "score",
                    "time",
                    "level",
                    "stage",
                    "lives",
                    "coin",
                    "press",
                    "continue",
                    "menu",
                    "option",
                    "sound",
                    "music",
                    "yes",
                    "no",
                    "save",
                    "load",
                    "exit",
                    "quit",
                    "help",
                    "back",
                    "next",
                    "select",
                    "enter",
                    "attack",
                    "jump",
                    "run",
                    "walk",
                    "fire",
                    "item",
                    "bonus",
                    "extra",
                    "power",
                    # Português
                    "jogador",
                    "pontos",
                    "vidas",
                    "fase",
                    "iniciar",
                    "continuar",
                    "sair",
                    "pausar",
                    "som",
                    "musica",
                    "sim",
                    "não",
                    "salvar",
                    "carregar",
                    "ajuda",
                    "voltar",
                    "proximo",
                    "selecionar",
                    "entrar",
                    "pular",
                    "correr",
                    "atirar",
                }
                text_lower = text_clean.lower()
                if any(word in text_lower for word in common_game_words):
                    return False, ""  # Válido - contém palavra de jogo

                # [OK] EXCEÇÃO 2: UI de jogo em MAIÚSCULAS (SCORE, 1UP, P1, LEVEL 1)
                game_ui_pattern = r"^[A-Z0-9\s\-]{2,15}$"
                if (
                    re.match(game_ui_pattern, text_clean)
                    and len(text_clean.split()) <= 3
                ):
                    # Verifica se tem pelo menos uma vogal
                    if any(c in "AEIOU" for c in text_clean):
                        return False, ""  # Válido - é UI de jogo

                # [OK] EXCEÇÃO 3: Frases com números (Player 1, Stage 1-1, Lives: 3)
                hud_pattern = r"(player|stage|level|world|area|lives|time|score|coins?)\s*[:=\-]?\s*[\d\-]+"
                if re.search(hud_pattern, text_clean, re.IGNORECASE):
                    return False, ""  # Válido - é HUD

                # ========== FILTROS DE BLOQUEIO ==========

                # [ERROR] BLOQUEIO 1: Endereços hexadecimais e ponteiros
                hex_patterns = [
                    r"0x[0-9A-Fa-f]+",  # 0x1234, 0xABCD
                    r"\$[0-9A-Fa-f]{2,}",  # $1234, $ABCD (notação assembly)
                    r"^[0-9A-F]{4,8}$",  # 1A2B, ABCD1234 (endereços puros)
                    r"[0-9]{2,}[><\|@#][0-9]",  # 07>37, 05@T (operadores + números)
                ]
                for pattern in hex_patterns:
                    if re.search(pattern, text_clean):
                        return True, "Endereço hexadecimal/ponteiro detectado"

                # [ERROR] BLOQUEIO 2: Sequências aleatórias (gibberish)
                # Detecta textos que não têm padrão de palavras reais
                if len(text_clean) >= 4:
                    # Conta transições consoante→consoante sem vogais
                    consonants = "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ"
                    consonant_runs = 0
                    for i in range(len(text_clean) - 2):
                        if (
                            text_clean[i] in consonants
                            and text_clean[i + 1] in consonants
                            and text_clean[i + 2] in consonants
                        ):
                            consonant_runs += 1

                    # Se >30% do texto são runs de 3+ consoantes = gibberish
                    if consonant_runs > len(text_clean) * 0.3:
                        return True, "Sequência aleatória (gibberish) detectada"

                # [ERROR] BLOQUEIO 3: Sem vogais (lixo binário)
                vowels = set("aeiouAEIOUàáâãéêíóôõúÀÁÂÃÉÊÍÓÔÕÚ")
                if not any(char in vowels for char in text_clean):
                    return True, "Sem vogais (lixo binário)"

                # [ERROR] BLOQUEIO 4: Proporção de caracteres especiais (>50% agora)
                special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`\\")
                special_count = sum(1 for char in text_clean if char in special_chars)
                if (
                    len(text_clean) > 0 and special_count / len(text_clean) > 0.5
                ):  # Reduzido para 50%
                    return (
                        True,
                        f">50% caracteres especiais ({special_count}/{len(text_clean)})",
                    )

                # [ERROR] BLOQUEIO 5: Padrões de lixo binário específicos
                garbage_patterns = [
                    (r"^[!@#$%^&*]{3,}", "3+ símbolos consecutivos"),
                    (r"^[A-Z]{10,}$", "10+ letras maiúsculas sem espaços"),
                    (r"^[0-9]{8,}$", "8+ dígitos consecutivos"),
                    (r"^[dD][A-F0-9]{4,}", "Padrão hexadecimal (dAdBdC)"),
                    (
                        r"[A-Z][a-z][A-Z][a-z][A-Z]",
                        "Padrão alternado suspeito (aBcDeF)",
                    ),
                    (r"^[^a-zA-Z]*$", "Somente símbolos/números sem letras"),
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
                        return (
                            True,
                            f"Repetição excessiva ({unique_chars} únicos de {total_chars})",
                        )

                # [ERROR] BLOQUEIO 7: Dados gráficos/tiles (padrões específicos)
                tile_patterns = [
                    r"^[a-z]{5,}$",  # ktuwv, ijklm (minúsculas consecutivas)
                    r"^[A-Z][a-z]{1,2}[A-Z]",  # AaBbC (padrão de encoding)
                    r"^\d+[A-Z]+\d+",  # 07A17, 84E86 (códigos)
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
                from difflib import SequenceMatcher

                if not raw_text or not isinstance(raw_text, str):
                    return True

                text_lower = raw_text.lower().strip()

                # Padrões de recusa (IA se recusando a traduzir)
                refusal_patterns = [
                    r"não posso",
                    r"i cannot",
                    r"i can\'t",
                    r"sorry",
                    r"desculpe",
                    r"i apologize",
                    r"peço desculpas",
                    r"i\'m unable",
                    r"não consigo",
                    r"i don\'t",
                    r"eu não",
                ]

                for pattern in refusal_patterns:
                    if re.search(pattern, text_lower):
                        return True  # É recusa, descartar

                # Detecta se IA repetiu instruções do prompt
                instruction_keywords = [
                    "1.",
                    "2.",
                    "3.",
                    "se o texto",
                    "if the text",
                    "instructions",
                ]
                if any(keyword in text_lower for keyword in instruction_keywords):
                    return True  # Repetiu instruções, descartar

                # Validação de similaridade: >95% igual ao original = não traduziu
                # Reduzido de 0.8 para 0.95 para aceitar traduções similares válidas
                # IMPORTANTE: faz strip em AMBOS para ignorar espaços no início/fim
                similarity = SequenceMatcher(
                    None, original_text.lower().strip(), text_lower
                ).ratio()
                if similarity > 0.95:
                    return True  # Muito similar, não traduziu de verdade

                return False  # Tradução válida

            def clean_translation(raw_text, original_text):
                """Remove prefixos indesejados preservando variáveis e tags"""
                if not raw_text or not isinstance(raw_text, str):
                    return original_text

                cleaned = raw_text.strip()

                # Remove prefixos comuns de modelos (case-insensitive)
                prefixes_to_remove = [
                    r"^sure[,:]?\s*",
                    r"^claro[,:]?\s*",
                    r"^here\s+(is|are)\s+(the\s+)?translation[s]?[:\s]*",
                    r"^aqui\s+está?\s+(a\s+)?tradução[:\s]*",
                    r"^translation[:\s]+",
                    r"^tradução[:\s]+",
                ]

                for prefix_pattern in prefixes_to_remove:
                    cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)

                # Remove dois-pontos inicial isolado
                cleaned = re.sub(r"^:\s*", "", cleaned)

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
                    self.log_signal.emit(
                        f"[WARN] Texto '{original_text[:30]}' ignorado. Motivo: {reason} (Filtro Entrada)"
                    )
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
                            "menu": (
                                "You are translating a GAME MENU. "
                                "Translate ALL items: START=Iniciar, CONTINUE=Continuar, OPTIONS=Opções, "
                                "EXIT=Sair, SAVE=Salvar, LOAD=Carregar, NEW GAME=Novo Jogo. "
                                "Keep translations SHORT."
                            ),
                            "dialog": (
                                "You are translating CHARACTER DIALOGUE. "
                                "Translate EVERYTHING to Portuguese - NO English words allowed. "
                                "PRESERVE the character's personality (sarcastic, grumpy, angry, funny). "
                                "Use natural Brazilian Portuguese speech."
                            ),
                            "tutorial": (
                                "You are translating a GAME TUTORIAL. "
                                "Translate button instructions: PRESS=Pressione, HOLD=Segure, PUSH=Empurre. "
                                "Be CLEAR and DIRECT. Use imperative form."
                            ),
                            "system": (
                                "You are translating SYSTEM MESSAGES. "
                                "Game Over=Fim de Jogo, Pause=Pausado, Score=Pontuação, "
                                "Lives=Vidas, Time=Tempo, Level=Fase, Continue=Continuar. "
                                "Keep SHORT for display limits."
                            ),
                            "story": (
                                "You are translating GAME STORY/NARRATIVE. "
                                "Use flowing narrative Portuguese. Maintain epic/dramatic tone. "
                                "Translate COMPLETELY - no English words."
                            ),
                        }

                        system_prompt = context_rules.get(
                            text_context,
                            (
                                "You are a professional video game translator. "
                                "Translate ALL text to Brazilian Portuguese. "
                                "NEVER leave any English words. "
                                "Keep ONLY technical codes like {VAR}, [NAME], <0A> unchanged."
                            ),
                        )

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
                                "temperature": 0.1,  # Muito baixa = determinístico
                                "num_predict": num_predict,
                                "top_p": 0.9,
                                "repeat_penalty": 1.1,
                                "num_ctx": 1024,  # Llama precisa mais contexto
                                "stop": ["<|eot_id|>", "<|end_of_text|>", "\n\n\n"],
                            },
                        }

                        # Timeout para Llama 3.1
                        timeout_value = 120 + (word_count * 2)

                        response = requests.post(
                            "http://127.0.0.1:11434/api/generate",
                            json=payload,
                            timeout=timeout_value,
                        )

                        if response.status_code == 200:
                            raw_translation = response.json().get("response", "")

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
                            translation = prompt_gen.extract_translation(
                                raw_translation, original_text
                            )

                            # Valida e corrige tradução
                            translation = prompt_gen.validate_and_fix_translation(
                                original_text, translation
                            )

                            # Pós-processamento: remove prefixos indesejados
                            translation = clean_translation(translation, original_text)

                            return index, translation
                        else:
                            # Erro HTTP: tenta novamente
                            last_error = f"HTTP {response.status_code}"
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(2**attempt)  # Backoff: 1s, 2s, 4s
                                continue
                            else:
                                self.log_signal.emit(
                                    f"[WARN] Texto {index} falhou após {MAX_RETRIES} tentativas: {last_error}"
                                )
                                return index, original_text

                    except requests.exceptions.ConnectionError as e:
                        last_error = "Conexão perdida com Ollama"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(
                                f"🔄 Texto {index}: Tentativa {attempt + 1}/{MAX_RETRIES} - Reconectando..."
                            )
                            time.sleep(2**attempt)  # Backoff exponencial
                            continue
                        else:
                            self.log_signal.emit(
                                f"[ERROR] Texto {index}: Ollama desconectou após {MAX_RETRIES} tentativas.\n"
                                f"   Verifique se 'ollama serve' ainda está rodando."
                            )
                            return index, original_text

                    except requests.exceptions.Timeout as e:
                        last_error = "Timeout após 180s"
                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(
                                f"⏱️ Texto {index}: Timeout - Tentativa {attempt + 1}/{MAX_RETRIES}"
                            )
                            time.sleep(2**attempt)
                            continue
                        else:
                            # Fallback: tenta tradução simplificada linha por linha
                            self.log_signal.emit(
                                f"🔄 Texto {index}: Tentando fallback..."
                            )
                            try:
                                lines = original_text.split("\n")
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
                                                "num_ctx": 1024,  # AUMENTADO
                                                "stop": ["<|eot_id|>", "\n\n"],
                                            },
                                        }
                                        resp = requests.post(
                                            "http://127.0.0.1:11434/api/generate",
                                            json=simple_payload,
                                            timeout=90,
                                        )
                                        if resp.status_code == 200:
                                            raw = resp.json().get("response", "")
                                            # Usa extrator robusto
                                            line_trans = prompt_gen.extract_translation(
                                                raw, line
                                            )
                                            line_trans = clean_translation(
                                                line_trans, line
                                            )
                                            translated_lines.append(line_trans)
                                        else:
                                            translated_lines.append(line)
                                    fallback_result = "\n".join(translated_lines)
                                    self.log_signal.emit(
                                        f"[OK] Texto {index}: Fallback OK"
                                    )
                                    return index, fallback_result
                            except Exception as fb_err:
                                self.log_signal.emit(
                                    f"[WARN] Fallback erro: {str(fb_err)[:50]}"
                                )

                            # Se fallback falhar: retorna original (não marca UNTRANSLATED)
                            self.log_signal.emit(
                                f"[WARN] Texto {index}: Mantendo original"
                            )
                            return index, original_text

                    except requests.exceptions.HTTPError as e:
                        last_error = f"HTTPError: {_sanitize_error(e)}"
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2**attempt)
                            continue
                        else:
                            self.log_signal.emit(
                                f"[WARN] Texto {index}: Erro HTTP - {str(e)[:80]}"
                            )
                            return index, original_text

                    except Exception as e:
                        # Erro inesperado: mostra COMPLETO (não apenas 50 chars)
                        error_type = type(e).__name__
                        error_msg = str(e)
                        last_error = f"{error_type}: {error_msg}"

                        if attempt < MAX_RETRIES - 1:
                            self.log_signal.emit(
                                f"[WARN] Texto {index}: {error_type} - Tentativa {attempt + 1}/{MAX_RETRIES}"
                            )
                            time.sleep(2**attempt)
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
            _moving_timestamps = collections.deque(maxlen=20)  # Taxa móvel

            self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
            try:
                for batch_start in range(0, len(unique_texts), BATCH_SIZE):
                    # [OK] CHECK FREQUENTE de interrupção
                    if not self._is_running:
                        self.log_signal.emit(
                            "[WARN] Tradução interrompida pelo usuário."
                        )
                        break

                    batch_end = min(batch_start + BATCH_SIZE, len(unique_texts))
                    batch = [
                        (i, unique_texts[i]) for i in range(batch_start, batch_end)
                    ]

                    # Submete batch
                    futures = {
                        self.executor.submit(translate_single, idx, text): idx
                        for idx, text in batch
                    }

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
                            translation = prompt_gen.extract_translation(
                                translation, original_text
                            )
                            translation = prompt_gen.validate_and_fix_translation(
                                original_text, translation
                            )

                        translated_unique[idx] = translation
                        completed += 1

                        # 📺 PAINEL EM TEMPO REAL
                        self.realtime_signal.emit(
                            original_text, translation, "Llama 3.1"
                        )

                        # Atualiza progresso
                        percent = int((completed / len(unique_texts)) * 100)
                        self.progress_signal.emit(percent)

                        # ETA por taxa móvel (últimos N itens confirmados)
                        _moving_timestamps.append(time.time())
                        remaining = len(unique_texts) - completed
                        if len(_moving_timestamps) >= 2:
                            window = _moving_timestamps[-1] - _moving_timestamps[0]
                            rate_items_min = (
                                (len(_moving_timestamps) - 1) / (window / 60.0)
                                if window > 0 else 0
                            )
                            eta_min = (
                                remaining / rate_items_min
                                if rate_items_min > 0 else 0
                            )
                            self.status_signal.emit(
                                f"[START] {completed}/{len(unique_texts)} ({percent}%) | "
                                f"ETA: {eta_min:.1f}min | {rate_items_min:.0f} items/min"
                            )
                        else:
                            self.status_signal.emit(
                                f"[START] {completed}/{len(unique_texts)} ({percent}%)"
                            )

                        # 🌡️ GPU BREATH: Respiro térmico MÁXIMO para GTX 1060
                        # 1.5s mantém GPU abaixo de 70°C (seguro)
                        time.sleep(1.5)  # PROTEÇÃO TÉRMICA: 1.5s entre traduções

                    # Log a cada batch
                    self.log_signal.emit(
                        f"[OK] Batch {batch_start//BATCH_SIZE + 1}/{(len(unique_texts)+BATCH_SIZE-1)//BATCH_SIZE} completo"
                    )

                    # 🌡️ RESPIRO TÉRMICO entre batches (resfriamento intensivo)
                    time.sleep(2.0)  # 2 segundos: GPU resfria antes do próximo batch

            finally:
                # Garante shutdown do executor
                self.executor.shutdown(wait=False)
                self.executor = None

            # === FASE 3: RECONSTRUÇÃO ===
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("🔧 FASE 3: RECONSTRUÇÃO DAS TRADUÇÕES")
            self.log_signal.emit("=" * 60)

            # Trata None em translated_unique
            for i in range(len(translated_unique)):
                if translated_unique[i] is None:
                    translated_unique[i] = unique_texts[i]  # Fallback para original

            # Reconstrói lista completa aplicando as traduções
            final_translations = optimizer.reconstruct_translations(
                translated_unique, lines, index_mapping
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
            with open(output_file, "w", encoding="utf-8") as f:
                for line in final_translations:
                    f.write(line + "\n")
                    written_count += 1

            self.log_signal.emit(f"[DEBUG] Escritas reais: {written_count}")
            self.log_signal.emit(f"[DEBUG] Linhas traduzidas: {translated_count}")
            self.log_signal.emit("[DEBUG] Arquivo salvo.")

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
    b"UnityFS": ("Unity Engine", "PC_GAME"),
    b"Unity": ("Unity Engine (Legacy)", "PC_GAME"),
    b"UE4": ("Unreal Engine 4", "PC_GAME"),
    b"UE3": ("Unreal Engine 3", "PC_GAME"),
    b"Source Engine": ("Source Engine (Valve)", "PC_GAME"),
    b"REFPACK": ("RefPack (EA Games)", "PC_GAME"),
    b"CryEngine": ("CryEngine", "PC_GAME"),
    b"Gamebryo": ("Gamebryo Engine", "PC_GAME"),
    b"RPG Maker": ("RPG Maker", "PC_GAME"),
    # === ARCHIVES & COMPRESSION ===
    b"PK\x03\x04": ("ZIP Archive", "ARCHIVE"),
    b"Rar!\x1a\x07\x00": ("RAR Archive", "ARCHIVE"),
    b"Rar!\x1a\x07\x01\x00": ("RAR5 Archive", "ARCHIVE"),
    b"7z\xbc\xaf\x27\x1c": ("7-Zip Archive", "ARCHIVE"),
    b"\x1f\x8b": ("GZIP Compressed", "ARCHIVE"),
    b"BZh": ("BZIP2 Compressed", "ARCHIVE"),
    b"\xfd7zXZ\x00": ("XZ Compressed", "ARCHIVE"),
    # === INSTALLERS ===
    b"Inno Setup": ("Inno Setup Installer", "INSTALLER"),
    b"Nullsoft": ("NSIS Installer (Nullsoft)", "INSTALLER"),
    b"InstallShield": ("InstallShield Installer", "INSTALLER"),
    b"MSCF": ("Microsoft Cabinet (CAB)", "INSTALLER"),
    b"szdd": ("MS Compress (SZDD)", "INSTALLER"),
    # === CLASSIC GAMES ===
    b"IWAD": ("Doom/Hexen (IWAD)", "PC_GAME"),
    b"PWAD": ("Doom Mod (PWAD)", "PC_GAME"),
    b"PAK": ("Quake PAK Archive", "PC_GAME"),
    b"WAD3": ("Half-Life WAD", "PC_GAME"),
    b"BSP": ("Quake BSP Map", "PC_GAME"),
    # === AUDIO/VIDEO (para ignorar) ===
    b"RIFF": ("RIFF Container (AVI/WAV)", "MEDIA"),
    b"ID3": ("MP3 Audio", "MEDIA"),
    b"OggS": ("OGG Audio", "MEDIA"),
    b"\x89PNG": ("PNG Image", "MEDIA"),
    b"\xff\xd8\xff": ("JPEG Image", "MEDIA"),
    b"GIF8": ("GIF Image", "MEDIA"),
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

    def __init__(
        self,
        api_key: str,
        input_file: str,
        target_language: str = "Portuguese (Brazil)",
        model: str = "gpt-3.5-turbo",
    ):
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
            if not REQUESTS_AVAILABLE:
                self.error_signal.emit(
                    "Biblioteca 'requests' não instalada. Execute: pip install requests"
                )
                return
            import time

            self.log_signal.emit(f"🤖 Iniciando ChatGPT ({self.model})...")
            self.status_signal.emit("Conectando à OpenAI...")

            # Lê arquivo de entrada
            with open(self.input_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Filtra linhas com formato [0xOFFSET] texto
            text_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("[0x") and "]" in line:
                    text_lines.append(line)

            total = len(text_lines)
            if total == 0:
                self.error_signal.emit("Nenhum texto encontrado no arquivo!")
                return

            self.log_signal.emit(f"[STATS] {total} textos para traduzir")

            # Prepara arquivo de saída
            output_file = self.input_file.replace(".txt", "_translated.txt")
            if output_file == self.input_file:
                output_file = self.input_file.replace(".txt", "") + "_translated.txt"

            translated_lines = []
            errors = 0

            # Processa em lotes de 10 para eficiência
            batch_size = 10

            for i in range(0, total, batch_size):
                if not self._is_running:
                    self.log_signal.emit("⏹️ Tradução interrompida pelo usuário")
                    break

                batch = text_lines[i : i + batch_size]
                batch_texts = []

                # Extrai apenas os textos (sem offsets)
                for line in batch:
                    match = re.match(r"^\[0x[0-9a-fA-F]+\]\s*(.*)$", line)
                    if match:
                        batch_texts.append(match.group(1))

                if not batch_texts:
                    continue

                # Monta prompt para ChatGPT
                texts_to_translate = "\n".join(
                    [f"{idx+1}. {t}" for idx, t in enumerate(batch_texts)]
                )

                prompt = f"""Translate the following game texts to {self.target_language}.
Keep the same numbering. Keep translations SHORT (same length or shorter than original).
Do NOT add explanations. Only return the translated lines with numbers.

{texts_to_translate}"""

                # Chama API da OpenAI
                try:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }

                    payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a professional game translator. Keep translations concise and natural.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    }

                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        translated_text = result["choices"][0]["message"]["content"]

                        # Parse das traduções
                        trans_lines = translated_text.strip().split("\n")
                        translations = {}

                        for tl in trans_lines:
                            # Tenta extrair número e texto
                            match = re.match(r"^(\d+)\.\s*(.*)$", tl.strip())
                            if match:
                                idx = int(match.group(1)) - 1
                                translations[idx] = match.group(2)

                        # Combina com offsets originais
                        for j, line in enumerate(batch):
                            offset_match = re.match(r"^(\[0x[0-9a-fA-F]+\])", line)
                            if offset_match:
                                offset = offset_match.group(1)
                                if j in translations:
                                    translated_lines.append(
                                        f"{offset} {translations[j]}"
                                    )
                                    # Emite para painel em tempo real
                                    self.realtime_signal.emit(
                                        batch_texts[j] if j < len(batch_texts) else "",
                                        translations[j],
                                        "ChatGPT",
                                    )
                                else:
                                    # Mantém original se tradução falhou
                                    translated_lines.append(line)
                    else:
                        error_msg = (
                            response.json()
                            .get("error", {})
                            .get("message", "Unknown error")
                        )
                        self.log_signal.emit(f"[WARN] Erro API: {error_msg}")
                        errors += 1
                        # Mantém originais em caso de erro
                        translated_lines.extend(batch)

                        if (
                            "rate_limit" in error_msg.lower()
                            or "quota" in error_msg.lower()
                        ):
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
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(translated_lines))

            self.log_signal.emit(
                f"[OK] Tradução concluída: {len(translated_lines)} linhas"
            )
            if errors > 0:
                self.log_signal.emit(f"[WARN] {errors} erros durante tradução")

            self.progress_signal.emit(100)
            self.status_signal.emit("Concluído!")
            self.finished_signal.emit(output_file)

        except Exception as e:
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
    progress_signal = pyqtSignal(str)  # Status em tempo real

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
                self.detection_complete.emit(
                    {
                        "type": "ERROR",
                        "platform": "Arquivo não encontrado",
                        "engine": "N/A",
                        "notes": "Path inválido",
                        "platform_code": None,
                    }
                )
                return

            file_ext = os.path.splitext(self.file_path)[1].lower()
            file_size = os.path.getsize(self.file_path)
            file_size_mb = file_size / (1024 * 1024)

            # ================================================================
            # LEITURA OTIMIZADA: Lê apenas setores críticos do arquivo
            # ================================================================
            header = b""
            snes_header_zone = b""  # 0x7FC0 região
            genesis_header_zone = b""  # 0x100 região
            ps1_sector_check = b""

            try:
                with open(self.file_path, "rb") as f:
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
                header = b""

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
                if category == "INSTALLER":
                    self.progress_signal.emit(f"🔍 Detectado: {engine_name_sig}")
                    self.progress_signal.emit(
                        "📦 Instalador detectado - Extração disponível"
                    )
                    self.progress_signal.emit(
                        "💡 DICA: Para melhores resultados, você pode instalar o jogo primeiro"
                    )

                    self.detection_complete.emit(
                        {
                            "type": "INSTALLER",
                            "platform": f"Instalador ({engine_name_sig})",
                            "engine": engine_name_sig,
                            "notes": f"Instalador detectado | {file_size_mb:.1f} MB | Extração disponível",
                            "platform_code": "INSTALLER",
                        }
                    )
                    return

                # === GAME ENGINES ===
                elif category == "PC_GAME":
                    self.progress_signal.emit(
                        f"🎮 Engine Detectada: {engine_name_sig} (Advanced Extraction Active)"
                    )

                    # Unity específico
                    if "Unity" in engine_name_sig:
                        notes = f"Unity Engine | {file_size_mb:.1f} MB | UTF-16LE + Asset Bundles"

                        self.detection_complete.emit(
                            {
                                "type": "PC_GAME",
                                "platform": "PC (Unity Engine)",
                                "engine": engine_name_sig,
                                "notes": notes,
                                "platform_code": "PC",
                            }
                        )
                        return

                    # Unreal específico
                    elif "Unreal" in engine_name_sig:
                        notes = f"Unreal Engine | {file_size_mb:.1f} MB | Localization Assets (.uasset)"

                        self.detection_complete.emit(
                            {
                                "type": "PC_GAME",
                                "platform": "PC (Unreal Engine)",
                                "engine": engine_name_sig,
                                "notes": notes,
                                "platform_code": "PC",
                            }
                        )
                        return

                    # Doom/Quake
                    elif "Doom" in engine_name_sig or "Quake" in engine_name_sig:
                        notes = f"{engine_name_sig} | {file_size_mb:.1f} MB | WAD/PAK Extraction"

                        self.detection_complete.emit(
                            {
                                "type": "PC_GAME",
                                "platform": "PC (Classic FPS)",
                                "engine": engine_name_sig,
                                "notes": notes,
                                "platform_code": "PC",
                            }
                        )
                        return

                # === ARCHIVES ===
                elif category == "ARCHIVE":
                    self.progress_signal.emit(f"📦 Detectado: {engine_name_sig}")
                    self.progress_signal.emit(
                        "💡 Extraia o arquivo primeiro e selecione o jogo"
                    )

                    self.detection_complete.emit(
                        {
                            "type": "ARCHIVE",
                            "platform": f"Arquivo Compactado ({engine_name_sig})",
                            "engine": engine_name_sig,
                            "notes": f"Arquivo compactado | {file_size_mb:.1f} MB | Extraia primeiro",
                            "platform_code": "ARCHIVE",
                        }
                    )
                    return

                # === MEDIA FILES (ignorar) ===
                elif category == "MEDIA":
                    self.progress_signal.emit(
                        f"[WARN] Arquivo de mídia detectado: {engine_name_sig}"
                    )

                    self.detection_complete.emit(
                        {
                            "type": "MEDIA",
                            "platform": "Arquivo de Mídia (não é jogo)",
                            "engine": engine_name_sig,
                            "notes": f"Arquivo de mídia | {file_size_mb:.1f} MB | Não contém textos traduzíveis",
                            "platform_code": "MEDIA",
                        }
                    )
                    return

            # ================================================================
            # DETECÇÃO LAYER 0: PRIORIDADE ABSOLUTA - EXTENSÃO .EXE
            # ================================================================
            # REGRA CRÍTICA: .exe SEMPRE é Windows, não importa bytes internos
            if file_ext in [".exe", ".dll", ".scr"]:
                category = (
                    "High Capacity"
                    if file_size_mb > 100
                    else "Medium Size" if file_size_mb > 10 else "Small"
                )

                pe_info = "Windows Executable"
                engine_name = f"Windows Executable ({category})"
                notes = f"{pe_info} | {file_size_mb:.1f} MB"

                # Valida PE header se possível
                if header[0:2] == b"MZ":
                    pe_offset = None
                    try:
                        if len(header) > 0x3C + 4:
                            pe_offset = int.from_bytes(
                                header[0x3C : 0x3C + 4], "little"
                            )
                        if (
                            pe_offset is not None
                            and pe_offset < len(header) - 4
                            and header[pe_offset : pe_offset + 4] == b"PE\x00\x00"
                        ):
                            pe_info = "Win32 PE Confirmed"
                            notes = f"{pe_info} | {file_size_mb:.1f} MB"
                    except (ValueError, TypeError, IndexError):
                        pass

                # Detecta DarkStone especificamente
                if (
                    b"DarkStone" in header
                    or b"DARKSTONE" in header
                    or b"jeRaff" in header
                ):
                    engine_name = "DarkStone Original (Delphine Software)"
                    notes = f"Action RPG ({file_size_mb:.1f} MB) | Desenvolvido em 1999"

                self.detection_complete.emit(
                    {
                        "type": "PC_GAME",
                        "platform": "PC (Windows)",
                        "engine": engine_name,
                        "notes": notes,
                        "platform_code": "PC",
                    }
                )
                return

            # ================================================================
            # DETECÇÃO LAYER 1: DNA BINÁRIO COM LIMITES DE SANIDADE
            # ================================================================

            # ═══ SUPER NINTENDO (SNES) ═══
            # TRAVA DE SANIDADE: SNES real nunca ultrapassa 12MB
            if file_ext in [".smc", ".sfc"] and file_size_mb <= 12:
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
                        rom_name = title_bytes.decode("ascii", errors="ignore").strip()
                        if not rom_name or len(rom_name) < 3:
                            rom_name = "SNES ROM"
                    except (UnicodeError, AttributeError, TypeError):
                        rom_name = "SNES ROM"

                    # Valida checksums
                    if len(checksum) == 2 and len(complement) == 2:
                        chk_val = int.from_bytes(checksum, "little")
                        cmp_val = int.from_bytes(complement, "little")
                        if (chk_val ^ cmp_val) == 0xFFFF:
                            is_valid_snes = True

                # Neutralidade V1: não exibir ROM Title, apenas tamanho
                detection_note = (
                    f"SNES ROM ({file_size_mb:.1f} MB)"
                    if is_valid_snes
                    else f"Console 16-bit ({file_size_mb:.1f} MB)"
                )

                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "Super Nintendo (16-bit)",
                        "engine": "SNES Cartridge",
                        "notes": detection_note,
                        "platform_code": "SNES",
                    }
                )
                return

            # ═══ SEGA GENESIS / MEGA DRIVE ═══
            # TRAVA DE SANIDADE: Genesis real nunca ultrapassa 8MB
            if (file_ext in [".md", ".gen", ".smd"] and file_size_mb <= 8) or (
                b"SEGA" in genesis_header_zone[:16] and file_size_mb <= 8
            ):
                rom_name = "Genesis ROM"

                # Tenta extrair nome do jogo em 0x150
                if len(genesis_header_zone) >= 200:
                    try:
                        title_bytes = genesis_header_zone[0x50:0x90]  # Domestic name
                        rom_name = title_bytes.decode("ascii", errors="ignore").strip()
                        if not rom_name or len(rom_name) < 3:
                            rom_name = "Genesis ROM"
                    except (UnicodeError, AttributeError, TypeError):
                        rom_name = "Genesis ROM"

                # Neutralidade V1: não exibir ROM Title
                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "Mega Drive / Genesis (16-bit)",
                        "engine": "Sega Console",
                        "notes": f"Genesis ROM ({file_size_mb:.1f} MB)",
                        "platform_code": "GENESIS",
                    }
                )
                return

            # ═══ PLAYSTATION 1 (CD-ROM) ═══
            if b"CD001" in ps1_sector_check or (
                file_ext in [".iso", ".img", ".bin", ".cue"] and file_size_mb > 600
            ):
                # Detecta se é CD ISO 9660
                is_iso9660 = b"CD001" in ps1_sector_check

                detection_note = (
                    "CD-ROM Image (ISO 9660)"
                    if is_iso9660
                    else f"Disc Image ({file_size_mb:.0f} MB)"
                )

                # Tenta detectar jogo específico no header
                game_signature = "PlayStation 1 Game"
                if b"SLUS" in header or b"SCES" in header or b"SCUS" in header:
                    game_signature = "PS1 Licensed Title"

                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "PlayStation 1 (CD-ROM)",
                        "engine": game_signature,
                        "notes": detection_note,
                        "platform_code": "PS1",
                    }
                )
                return

            # ═══ NINTENDO NES ═══
            # TRAVA DE SANIDADE: NES real nunca ultrapassa 2MB
            if (header[0:4] == b"NES\x1a" or file_ext == ".nes") and file_size_mb <= 2:
                # iNES header contém informações
                prg_rom_size = 0
                chr_rom_size = 0
                mapper = 0

                if len(header) >= 16 and header[0:4] == b"NES\x1a":
                    prg_rom_size = header[4] * 16  # KB
                    chr_rom_size = header[5] * 8  # KB
                    mapper = ((header[6] >> 4) & 0x0F) | (header[7] & 0xF0)

                    notes = f"Mapper: {mapper} | PRG: {prg_rom_size}KB | CHR: {chr_rom_size}KB"
                else:
                    notes = f"Console 8-bit ({file_size_mb:.1f} MB)"

                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "Nintendo Entertainment System (8-bit)",
                        "engine": "NES iNES Format",
                        "notes": notes,
                        "platform_code": "NES",
                    }
                )
                return

            # ================================================================
            # DETECÇÃO LAYER 2: ENGINES DE PC (DNA de Software)
            # ================================================================

            # ═══ DOOM / HEXEN (WAD Files) ═══
            if header[0:4] in (b"IWAD", b"PWAD"):
                wad_type = "Internal WAD" if header[0:4] == b"IWAD" else "Patch WAD"
                num_lumps = 0
                if len(header) >= 12:
                    num_lumps = int.from_bytes(header[4:8], "little")

                self.detection_complete.emit(
                    {
                        "type": "PC_GAME",
                        "platform": "PC (DOS/Windows)",
                        "engine": "id Tech 1 (Doom Engine)",
                        "notes": f"{wad_type} | {num_lumps} lumps",
                        "platform_code": "PC",
                    }
                )
                return

            # ═══ UNITY ENGINE ═══
            if (
                b"UnityFS" in header[:512]
                or b"UnityWeb" in header[:512]
                or b"UnityRaw" in header[:512]
            ):
                unity_version = "Unknown"

                # Tenta extrair versão do Unity
                if b"UnityFS" in header:
                    try:
                        # Versão geralmente aparece após "UnityFS"
                        version_section = header[
                            header.find(b"UnityFS") : header.find(b"UnityFS") + 100
                        ]
                        if b"201" in version_section or b"202" in version_section:
                            unity_version = "2017-2024"
                    except (ValueError, TypeError, IndexError):
                        pass

                self.detection_complete.emit(
                    {
                        "type": "PC_GAME",
                        "platform": "PC (Unity Engine)",
                        "engine": f"Unity {unity_version}",
                        "notes": f"Modern game engine ({file_size_mb:.1f} MB)",
                        "platform_code": "PC",
                    }
                )
                return

            # ═══ UNREAL ENGINE ═══
            if header[0:4] == b"\xc1\x83\x2a\x9e" or b"Unreal" in header[:512]:
                self.detection_complete.emit(
                    {
                        "type": "PC_GAME",
                        "platform": "PC (Unreal Engine)",
                        "engine": "Unreal Engine",
                        "notes": f"AAA game engine ({file_size_mb:.1f} MB)",
                        "platform_code": "PC",
                    }
                )
                return

            # ═══ WINDOWS PE EXECUTABLES (Generic) ═══
            if header[0:2] == b"MZ" and file_ext in [".exe", ".dat"]:
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
                        pe_offset = int.from_bytes(header[0x3C : 0x3C + 4], "little")
                        if pe_offset < len(header) - 4:
                            pe_signature = header[pe_offset : pe_offset + 4]
                        if pe_signature == b"PE\x00\x00":
                            pe_info = "Win32 PE Confirmed"
                except (ValueError, TypeError, IndexError):
                    pass

                self.detection_complete.emit(
                    {
                        "type": "PC_GAME",
                        "platform": "PC (Windows)",
                        "engine": f"Windows Executable ({category})",
                        "notes": f"{pe_info} | {file_size_mb:.1f} MB",
                        "platform_code": "PC",
                    }
                )
                return

            # ================================================================
            # DETECÇÃO LAYER 3: Fallback por extensão
            # ================================================================

            # Game Boy / GBA
            if file_ext in [".gb", ".gbc"]:
                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "Game Boy / Game Boy Color (8-bit)",
                        "engine": "Nintendo Handheld",
                        "notes": f"Portátil ({file_size_mb:.1f} MB)",
                        "platform_code": "GB",
                    }
                )
                return

            if file_ext == ".gba":
                self.detection_complete.emit(
                    {
                        "type": "ROM",
                        "platform": "Game Boy Advance (32-bit)",
                        "engine": "Nintendo Handheld Advanced",
                        "notes": f"Portátil avançado ({file_size_mb:.1f} MB)",
                        "platform_code": "GBA",
                    }
                )
                return

            # Fallback genérico
            self.detection_complete.emit(
                {
                    "type": "GENERIC",
                    "platform": f'Arquivo {file_ext.upper()[1:] if file_ext else "Binário"}',
                    "engine": f"Binary File ({file_size_mb:.1f} MB)",
                    "notes": "Sistema fará melhor esforço na extração",
                    "platform_code": None,
                }
            )

        except Exception as e:
            self.detection_complete.emit(
                {
                    "type": "ERROR",
                    "platform": "Erro ao analisar",
                    "engine": "N/A",
                    "notes": f"{_sanitize_error(e)} | {_sanitize_error(traceback.format_exc()[:200])}",
                    "platform_code": None,
                }
            )


class ReinsertionWorker(QThread):
    """Worker dedicado para Reinserção. Thread-safe."""

    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        rom_path: str,
        translated_path: str,
        output_rom_path: str,
        force_blocked: bool = False,
    ):
        super().__init__()
        self.rom_path = rom_path
        self.translated_path = translated_path
        self.output_rom_path = output_rom_path
        self.force_blocked = force_blocked

    def run(self):
        try:
            self.status_signal.emit("Preparando arquivos...")
            self.progress_signal.emit(0)

            # ================================================================
            # DETECÇÃO AUTOMÁTICA: PC Game / Sega / ROM de Console
            # ================================================================
            file_ext = os.path.splitext(self.rom_path)[1].lower()

            if file_ext in [".exe", ".dll", ".dat"]:
                # Usa módulo PC Reinserter
                self.log_signal.emit("🖥️ Detectado: PC Game - usando PC Reinserter")
                self._reinsert_pc_game()
                return
            elif file_ext in [".sms", ".md", ".gen", ".smd"]:
                # Usa módulo Sega Reinserter
                self.log_signal.emit("🎮 Detectado: Sega ROM - usando Sega Reinserter")
                self._reinsert_sega_rom()
                return
            else:
                # Usa módulo ROM tradicional
                self.log_signal.emit(
                    "🎮 Detectado: Console ROM - usando reinserção tradicional"
                )

            with open(
                self.translated_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                lines = f.readlines()

            shutil.copyfile(self.rom_path, self.output_rom_path)

            rom_size = os.path.getsize(self.output_rom_path)

            with open(self.output_rom_path, "r+b") as rom_file:
                total_lines = len(lines)

                for i, line in enumerate(lines):
                    if self.isInterruptionRequested():
                        self.log_signal.emit("Reinserção interrompida pelo usuário.")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("["):
                        try:
                            match = re.match(r"^\[(0x[0-9a-fA-F]+)\]\s*(.*)$", line)
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
                                encoded_text = new_text_with_codes.encode(
                                    "latin-1", errors="ignore"
                                )

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
            try:
                crc32_out = _crc32_file(self.output_rom_path)
                size_out = os.path.getsize(self.output_rom_path)
                self.log_signal.emit(
                    f"[OK] ROM salva com sucesso | CRC32={crc32_out} | ROM_SIZE={size_out}"
                )
            except Exception:
                self.log_signal.emit("[OK] ROM salva com sucesso")
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
            with open(rom_path, "r+b") as f:
                rom_data = bytearray(f.read())
                rom_size = len(rom_data)

                # Detecta se tem header SMC (512 bytes)
                has_header = rom_size % 1024 == 512
                header_offset = 0x200 if has_header else 0x000

                # Detecta tipo de mapeamento (LoROM vs HiROM)
                map_mode_offset = 0x7FD5 + header_offset
                if map_mode_offset < rom_size:
                    map_mode = rom_data[map_mode_offset]
                    is_hirom = map_mode in [0x21, 0x31]
                else:
                    is_hirom = False

                # Define offset do checksum
                if is_hirom:
                    checksum_offset = 0xFFDC + header_offset
                else:
                    checksum_offset = 0x7FDC + header_offset

                # Valida offset
                if checksum_offset + 4 > rom_size:
                    self.log_signal.emit("[WARN] ROM muito pequena para checksum SNES")
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
                progress_callback,
            )

            if result["success"]:
                self.log_signal.emit(f"\n{'='*60}")
                self.log_signal.emit("[OK] REINSERÇÃO PC CONCLUÍDA!")
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit("[STATS] Estatísticas de Processamento:")
                self.log_signal.emit(f"   • Strings inseridas: {result['modified']}")
                self.log_signal.emit(
                    f"   • Strings realocadas: {result.get('relocated', 0)}"
                )
                self.log_signal.emit(f"   • Strings ignoradas: {result['skipped']}")
                self.log_signal.emit(
                    f"   • Expansão do arquivo: +{result.get('expansion', 0):,} bytes"
                )

                # Estatísticas de ponteiros
                if "pointer_stats" in result:
                    pstats = result["pointer_stats"]
                    self.log_signal.emit("\n🔗 Análise de Ponteiros:")
                    self.log_signal.emit(
                        f"   • Realocações com ponteiros: {pstats.get('relocated_with_pointers', 0)}"
                    )
                    self.log_signal.emit(
                        f"   • Realocações sem ponteiros: {pstats.get('relocated_no_pointers', 0)}"
                    )
                    self.log_signal.emit(
                        f"   • Taxa de detecção: {pstats.get('pointer_detection_rate', 0):.1f}%"
                    )

                    if pstats.get("relocated_no_pointers", 0) > 0:
                        self.log_signal.emit(
                            "\nℹ️  NOTA: Strings sem ponteiros detectados podem ser:"
                        )
                        self.log_signal.emit(
                            "   • Strings inline (não referenciadas por ponteiros)"
                        )
                        self.log_signal.emit("   • Dados de interface hard-coded")
                        self.log_signal.emit("   • Recursos estáticos do jogo")

                if result.get("errors"):
                    self.log_signal.emit("\n[WARN] Primeiros erros detectados:")
                    for error in result["errors"][:5]:
                        self.log_signal.emit(f"  • {error}")

                self.log_signal.emit(f"{'='*60}\n")
                self.finished_signal.emit()
            else:
                self.error_signal.emit(result.get("error", "Erro desconhecido"))

        except ImportError:
            self.error_signal.emit(
                "Módulo pc_game_reinserter não encontrado. Reinstale o software."
            )
        except Exception as e:
            error_details = _sanitize_error(traceback.format_exc())
            self.log_signal.emit(f"Erro PC Reinserter: {error_details}")
            self.error_signal.emit(_sanitize_error(e))

    def _pair_txt_with_jsonl(self) -> dict:
        """Pareia traduções em TXT puro com metadados do JSONL de extração.

        Quando o arquivo traduzido é texto simples (uma linha por tradução,
        sem cabeçalhos [key@...]), busca o JSONL original de extração
        (``*_pure_text.jsonl``) e o arquivo otimizado (``*_optimized.txt``)
        para reconstruir o dicionário ``{key: tradução}`` que o SegaReinserter
        precisa.
        """
        import json as _json

        translated_path = Path(self.translated_path)

        # --- 1. Localiza o JSONL de extração ---
        search_dirs = [translated_path.parent]
        interno = translated_path.parent / f"{translated_path.parent.name}_interno"
        if interno.is_dir():
            search_dirs.append(interno)
        if translated_path.parent.parent.is_dir():
            search_dirs.append(translated_path.parent.parent)

        jsonl_path = None
        for d in search_dirs:
            try:
                for f in sorted(d.iterdir()):
                    if f.suffix.lower() == ".jsonl" and "pure_text" in f.name.lower():
                        jsonl_path = f
                        break
            except (PermissionError, OSError):
                continue
            if jsonl_path:
                break

        if not jsonl_path:
            self.log_signal.emit("[WARN] JSONL de extração não encontrado")
            return {}

        self.log_signal.emit(f"[INFO] JSONL encontrado: {jsonl_path.name}")

        # --- 2. Lê entradas do JSONL ---
        jsonl_entries = []
        for ln in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                jsonl_entries.append(_json.loads(ln))
            except _json.JSONDecodeError:
                continue

        if not jsonl_entries:
            return {}

        # --- 3. Lê linhas traduzidas ---
        translated_lines = translated_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()

        # --- 4. Lê arquivo otimizado (ponte entre JSONL e traduzido) ---
        optimized_path = Path(
            str(self.translated_path).replace("_translated.txt", "_optimized.txt")
        )
        optimized_lines = None
        if optimized_path.exists():
            optimized_lines = optimized_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()

        # --- 5. Índice text_src → entradas JSONL ---
        src_index: dict = {}
        for entry in jsonl_entries:
            src = (entry.get("text_src") or entry.get("text") or "").strip()
            if src:
                src_index.setdefault(src, []).append(entry)

        def _entry_key(entry):
            """Extrai a chave (id ou offset) de uma entrada JSONL."""
            off = entry.get("offset", 0)
            if isinstance(off, str):
                s = off.strip()
                try:
                    off = int(s, 16) if s.lower().startswith("0x") else int(s)
                except ValueError:
                    off = 0
            if entry.get("id") is not None:
                return str(entry["id"])
            return f"0x{off:X}"

        translations: dict = {}

        if optimized_lines is not None:
            # Pareamento via arquivo otimizado: optimized[i] ↔ translated[i]
            trans_idx = 0
            for opt_line in optimized_lines:
                opt_text = opt_line.strip()
                if not opt_text:
                    if (
                        trans_idx < len(translated_lines)
                        and not translated_lines[trans_idx].strip()
                    ):
                        trans_idx += 1
                    continue

                if trans_idx >= len(translated_lines):
                    break

                trans_text = translated_lines[trans_idx].strip()
                trans_idx += 1

                if not trans_text:
                    continue

                entries = src_index.get(opt_text, [])
                if entries:
                    entry = entries.pop(0)
                    translations[_entry_key(entry)] = trans_text
        else:
            # Sem otimizado: pareamento direto JSONL[i] → translated[i]
            trans_idx = 0
            for entry in jsonl_entries:
                if trans_idx >= len(translated_lines):
                    break
                trans_text = translated_lines[trans_idx].strip()
                trans_idx += 1
                if not trans_text:
                    continue
                translations[_entry_key(entry)] = trans_text

        return translations

    def _reinsert_sega_rom(self):
        """
        Reinserção específica para Sega ROMs (Master System, Mega Drive).
        Usa módulo sega_reinserter.py
        """
        try:
            # Tenta importar do caminho relativo
            current_dir = os.path.dirname(os.path.abspath(__file__))
            core_dir = os.path.join(os.path.dirname(current_dir), "core")
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)

            from core.sega_reinserter import SegaReinserter

            self.status_signal.emit("Carregando ROM Sega...")
            self.progress_signal.emit(10)

            # Cria reinsertor
            reinserter = SegaReinserter(self.rom_path)

            self.status_signal.emit("Carregando traduções...")
            self.progress_signal.emit(30)

            # Carrega traduções
            translations = reinserter.load_translations(self.translated_path)

            # Fallback: se o arquivo traduzido é TXT puro (sem cabeçalhos [key]),
            # tenta parear com o JSONL de extração para reconstruir o mapeamento
            if not translations and self.translated_path.lower().endswith(".txt"):
                self.log_signal.emit(
                    "[INFO] TXT sem cabeçalhos de bloco. "
                    "Pareando com JSONL de extração..."
                )
                translations = self._pair_txt_with_jsonl()
                if translations:
                    self.log_signal.emit(
                        f"[OK] {len(translations)} traduções pareadas via JSONL"
                    )

            if not translations:
                self.error_signal.emit("Nenhuma tradução encontrada no arquivo")
                return

            self.log_signal.emit(f"[STATS] {len(translations)} textos para reinserir")
            self.status_signal.emit(f"Reinserindo {len(translations)} textos...")
            self.progress_signal.emit(50)

            # Executa reinserção
            if self.force_blocked:
                self.log_signal.emit(
                    "⚠️ force_blocked ativo: tentando reinserir itens marcados como não seguros"
                )
            success, message = reinserter.reinsert(
                translations,
                self.output_rom_path,
                create_backup=True,
                force_blocked=self.force_blocked,
            )

            self.progress_signal.emit(90)

            if success:
                self.log_signal.emit(f"\n{'='*60}")
                self.log_signal.emit("[OK] REINSERÇÃO SEGA CONCLUÍDA!")
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit("[STATS] Estatísticas:")
                self.log_signal.emit(f"   • Inseridos: {reinserter.stats['inserted']}")
                self.log_signal.emit(f"   • Truncados: {reinserter.stats['truncated']}")
                self.log_signal.emit(f"   • Ignorados: {reinserter.stats['skipped']}")
                try:
                    crc32_out = _crc32_file(self.output_rom_path)
                    size_out = os.path.getsize(self.output_rom_path)
                    self.log_signal.emit(
                        f"📂 ROM: CRC32={crc32_out} | ROM_SIZE={size_out}"
                    )
                except Exception:
                    self.log_signal.emit("📂 ROM pronta.")
                self.log_signal.emit(f"{'='*60}\n")

                self.progress_signal.emit(100)
                self.status_signal.emit("Concluído!")
                self.finished_signal.emit()
            else:
                self.error_signal.emit(message)

        except ImportError as e:
            self.log_signal.emit(f"[WARN] Erro de importação: {_sanitize_error(e)}")
            self.error_signal.emit(
                "Módulo sega_reinserter não encontrado. Reinstale o software."
            )
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
    CORE_DIR = FRAMEWORK_DIR / "core"
    EXTRACTION_DIR = CORE_DIR  # compat: algumas rotas usam ProjectConfig.EXTRACTION_DIR
    SCRIPTS_DIR = BASE_DIR.parent / "Scripts principais"
    CONFIG_FILE = BASE_DIR / "translator_config.json"
    FORENSIC_CRC_DB_FILE = BASE_DIR / "forensic_crc_db.json"
    I18N_DIR = BASE_DIR.parent / "i18n"
    # --- COLE AQUI (Mantenha o recuo/indentação igual ao de cima) ---

    # Plataformas ordenadas por ano de lançamento
    PLATFORMS = {
        # --- 1977 ---
        "Atari 2600 (1977)": {
            "code": "atari",
            "ready": False,
            "label": "platform_atari",
        },
        # --- 1983 ---
        "Nintendo (NES) (1983)": {
            "code": "nes",
            "ready": False,
            "label": "platform_nes",
        },
        # --- 1985 ---
        "Sega Master System (1985)": {
            "code": "sms",
            "ready": True,
            "label": "platform_sms",
        },
        # --- 1988 ---
        "Sega Mega Drive (1988)": {
            "code": "md",
            "ready": False,
            "label": "platform_md",
        },
        # --- 1989 ---
        "Game Boy (1989)": {"code": "gb", "ready": False, "label": "platform_gb"},
        # --- 1990 ---
        "Super Nintendo (SNES) (1990)": {
            "code": "snes",
            "ready": False,
            "label": "platform_snes",
        },
        "Neo Geo (1990)": {"code": "neo", "ready": False, "label": "platform_neo"},
        # --- 1991 ---
        "Sega CD (1991)": {"code": "scd", "ready": False, "label": "platform_scd"},
        # --- 1994 ---
        "PlayStation 1 (PS1) (1994)": {
            "code": "ps1",
            "ready": False,
            "label": "platform_ps1",
        },
        "Sega Saturn (1994)": {"code": "sat", "ready": False, "label": "platform_sat"},
        # --- 1996 ---
        "Nintendo 64 (N64) (1996)": {
            "code": "n64",
            "ready": False,
            "label": "platform_n64",
        },
        # --- 1998 ---
        "Game Boy Color (GBC) (1998)": {
            "code": "gbc",
            "ready": False,
            "label": "platform_gbc",
        },
        "Sega Dreamcast (1998)": {"code": "dc", "ready": False, "label": "platform_dc"},
        # --- 2000 ---
        "PlayStation 2 (PS2) (2000)": {
            "code": "ps2",
            "ready": False,
            "label": "platform_ps2",
        },
        # --- 2001 ---
        "Game Boy Advance (GBA) (2001)": {
            "code": "gba",
            "ready": False,
            "label": "platform_gba",
        },
        "Nintendo GameCube (2001)": {
            "code": "gc",
            "ready": False,
            "label": "platform_gc",
        },
        "Xbox Clássico (2001)": {
            "code": "xbox",
            "ready": False,
            "label": "platform_xbox",
        },
        # --- 2004 ---
        "Nintendo DS (NDS) (2004)": {
            "code": "nds",
            "ready": False,
            "label": "platform_nds",
        },
        # --- 2005 ---
        "Xbox 360 (2005)": {"code": "x360", "ready": False, "label": "platform_x360"},
        # --- 2006 ---
        "PlayStation 3 (PS3) (2006)": {
            "code": "ps3",
            "ready": False,
            "label": "platform_ps3",
        },
        "Nintendo Wii (2006)": {"code": "wii", "ready": False, "label": "platform_wii"},
        # --- 2011 ---
        "Nintendo 3DS (2011)": {"code": "3ds", "ready": False, "label": "platform_3ds"},
        # --- 2012 ---
        "Nintendo Wii U (2012)": {
            "code": "wiiu",
            "ready": False,
            "label": "platform_wiiu",
        },
        # --- 2013 ---
        "PlayStation 4 (PS4) (2013)": {
            "code": "ps4",
            "ready": False,
            "label": "platform_ps4",
        },
        # --- 2017 ---
        "Nintendo Switch (2017)": {
            "code": "switch",
            "ready": False,
            "label": "platform_switch",
        },
        # --- 2020 ---
        "PlayStation 5 (PS5) (2020)": {
            "code": "ps5",
            "ready": False,
            "label": "platform_ps5",
        },
        # --- PC ---
        "MS-DOS (PC Antigo)": {"code": "dos", "ready": False, "label": "platform_dos"},
        "PC Games (Windows)": {"code": "pc", "ready": False, "label": "platform_pc"},
        "PC Games (Linux)": {
            "code": "linux",
            "ready": False,
            "label": "platform_linux",
        },
        "PC Games (Mac)": {"code": "mac", "ready": False, "label": "platform_mac"},
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
        "🇳🇱 Nederlands (Dutch)": "nl",
    }

    FONT_FAMILIES = {
        "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
        "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
        "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
        "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
        "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
        "Arial": "Arial, sans-serif",
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
        "Polonês (Polski)": "pl",
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
        "Русский (Russian)": "ru",
    }
    THEMES = {
        "Preto (Black)": {
            "window": "#000000",
            "text": "#f2f2f2",
            "button": "#000000",
            "accent": "#D4AF37",
        },
        "Cinza (Gray)": {
            "window": "#2F2F2F",
            "text": "#EDEDED",
            "button": "#444444",
            "accent": "#D4AF37",
        },
    }

    # Mapping between internal theme keys and translation keys
    THEME_TRANSLATION_KEYS = {
        "Preto (Black)": "theme_black",
        "Cinza (Gray)": "theme_gray",
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
                with open(json_file, "r", encoding="utf-8") as f:
                    translations = json.load(f)
                    cls._translations_cache[lang_code] = translations
                    return translations
            except Exception as e:
                print(f"[WARN] Failed to load {lang_code}.json: {_sanitize_error(e)}")

        # Fallback to English if not 'en' itself
        if lang_code != "en":
            return cls.load_translations("en")

        return {}

    @classmethod
    def clear_translations_cache(cls, lang_code: str | None = None) -> None:
        """Limpa o cache de traduções (todas ou uma língua específica)."""
        if lang_code:
            cls._translations_cache.pop(lang_code, None)
        else:
            cls._translations_cache.clear()

    # ROADMAP: Future platforms (not shown in main dropdown)
    PLATFORMS_ROADMAP = {
        "PlayStation": ["PS2", "PS3", "PS4", "PS5"],
        "Nintendo Classic": ["NES", "N64", "GameCube", "Wii", "Wii U", "Switch"],
        "Nintendo Portable": [
            "Game Boy",
            "Game Boy Color",
            "Game Boy Advance",
            "Nintendo DS",
            "3DS",
        ],
        "Sega": ["Master System", "Mega Drive/Genesis", "Saturn", "Dreamcast"],
        "Xbox": ["Xbox", "Xbox 360", "Xbox One", "Xbox Series X/S"],
        "Other": ["Atari 2600", "Neo Geo", "PC Linux", "PC macOS"],
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
                "Other": "Outros",
            },
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
                "Other": "Other",
            },
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
                "Other": "Otros",
            },
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
                "Other": "Autres",
            },
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
                "Other": "Andere",
            },
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
                "Other": "Altro",
            },
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
                "Other": "その他",
            },
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
                "Other": "기타",
            },
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
                "Other": "其他",
            },
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
                "Other": "Другое",
            },
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
                "Other": "أخرى",
            },
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
                "Other": "अन्य",
            },
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
                "Other": "Diğer",
            },
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
                "Other": "Inne",
            },
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
                "Other": "Andere",
            },
        },
    }

    FONT_FAMILIES = {
        "Padrão (Segoe UI + CJK Fallback)": "Segoe UI, Malgun Gothic, Yu Gothic UI, Microsoft JhengHei UI, sans-serif",
        "Segoe UI Semilight": "Segoe UI Semilight, Segoe UI, sans-serif",
        "Malgun Gothic (Korean)": "Malgun Gothic, sans-serif",
        "Yu Gothic UI (Japanese)": "Yu Gothic UI, Yu Gothic, sans-serif",
        "Microsoft JhengHei UI (Chinese)": "Microsoft JhengHei UI, Microsoft JhengHei, sans-serif",
        "Arial": "Arial, sans-serif",
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
        "Polonês (Polski)": "pl",
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
        "Русский (Russian)": "ru",
    }

    THEMES = {
        "Preto (Black)": {
            "window": "#000000",
            "text": "#f2f2f2",
            "button": "#000000",
            "accent": "#D4AF37",
        },
        "Cinza (Gray)": {
            "window": "#2F2F2F",
            "text": "#EDEDED",
            "button": "#444444",
            "accent": "#D4AF37",
        },
    }

    TRANSLATIONS = {
        "pt": {
            "title": "Extração - Otimização - Tradução IA - Reinserção",
            "tab1": "🔍 1. Extração",
            "tab2": "🎨 2. Laboratório Gráfico (Beta)",
            "tab3": "🧠 3. Tradução",
            "tab4": "📥 4. Reinserção",
            "tab5": "⚙️ 5. Configurações",
            "platform": "Plataforma:",
            "rom_file": "Arquivo ROM",
            "no_rom": "[WARN] Nenhuma ROM selecionada",
            "select_rom": "Selecionar ROM",
            "extract_texts": "📄 Extrair Textos",
            "optimize_data": "🧹 Otimizar Dados",
            "extraction_progress": "Progresso da Extração",
            "optimization_progress": "Progresso da Otimização",
            "waiting": "Aguardando início...",
            "language_config": "🌍 Configuração de Idiomas",
            "source_language": "📖 Idioma de Origem (ROM)",
            "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Tradução",
            "api_config": "Configuração de API",
            "api_key": "API Key:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Usar cache de traduções",
            "translation_progress": "Progresso da Tradução",
            "translate_ai": "🤖 Traduzir com IA",
            "stop_translation": "🛑 Parar Tradução",
            "original_rom": "ROM Original",
            "translated_file": "Arquivo Traduzido",
            "select_file": "Selecionar Arquivo",
            "output_rom": "💾 ROM Traduzida (Saída)",
            "reinsertion_progress": "Progresso da Reinserção",
            "reinsert": "Reinserir Tradução",
            "theme": "🎨 Tema Visual",
            "ui_language": "🌐 Idioma da Interface",
            "font_family": "🔤 Fonte da Interface",
            "log": "Log de Operações",
            "restart": "Reiniciar",
            "exit": "Sair",
            "developer": "Desenvolvido por: Celso (Programador Solo)",
            "in_dev": "EM DESENVOLVIMENTO",
            "file_to_translate": "📄 Arquivo para Traduzir (Otimizado)",
            "no_file": "Nenhum arquivo selecionado",
            "help_support": "🆘 Ajuda e Suporte",
            "manual_guide": "📘 Guia de Uso Profissional:",
            "contact_support": "📧 Dúvidas? Entre em contato:",
            "btn_stop": "Parar Tradução",
            "btn_close": "Fechar",
            "roadmap_item": "Próximos Consoles (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas em desenvolvimento:",
            "theme_black": "Preto",
            "theme_gray": "Cinza",
            "theme_white": "Branco",
            "gfx_toolbar": "Controles de Visualização",
            "gfx_format": "Formato:",
            "gfx_zoom": "Zoom:",
            "gfx_palette": "Paleta:",
            "gfx_offset": "Endereço (Hex):",
            "gfx_tiles_per_row": "Largura:",
            "gfx_num_tiles": "Núm. Tiles:",
            "gfx_canvas": "Visualizador de Tiles",
            "gfx_load_rom": "📂 Carregue uma ROM na Aba 1 para visualizar aqui",
            "gfx_navigation_hint": "Dica: Use as setas do teclado para navegar. Scroll para Zoom.",
            "gfx_analysis": "Ferramentas de Análise",
            "gfx_editing": "Ferramentas de Edição",
            "gfx_btn_sniffer": "🔍 Detectar Fontes",
            "gfx_btn_entropy": "[STATS] Scanner de Compressão",
            "gfx_btn_export": "📥 Exportar PNG",
            "gfx_btn_import": "📤 Importar e Reinserir",
            "gfx_entropy_group": "Análise de Entropia de Shannon",
            "gfx_entropy_click": "Clique em 'Scanner de Entropia' para analisar...",
            "gfx_btn_prev": "◀ Página Anterior",
            "gfx_btn_next": "Próxima Página ▶",
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
            "IMPORTANTE: Não adicione cores novas! Use apenas as cores existentes no PNG exportado.",
        },
        "en": {
            "title": "Extraction - Optimization - AI Translation - Reinsertion",
            "tab1": "🔍 1. Extraction",
            "tab2": "🎨 2. Graphics Lab (Beta)",
            "tab3": "🧠 3. Translation",
            "tab4": "📥 4. Reinsertion",
            "tab5": "⚙️ 5. Settings",
            "platform": "Platform:",
            "rom_file": "ROM File",
            "no_rom": "[WARN] No ROM selected",
            "select_rom": "Select ROM",
            "extract_texts": "📄 Extract Texts",
            "optimize_data": "🧹 Optimize Data",
            "extraction_progress": "Extraction Progress",
            "optimization_progress": "Optimization Progress",
            "waiting": "Waiting...",
            "language_config": "🌍 Language Configuration",
            "source_language": "📖 Source Language (ROM)",
            "target_language": "🎯 Target Language",
            "translation_mode": "Translation Mode",
            "api_config": "API Configuration",
            "api_key": "API Key:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Use translation cache",
            "translation_progress": "Translation Progress",
            "translate_ai": "🤖 Translate with AI",
            "stop_translation": "🛑 Stop Translation",
            "original_rom": "Original ROM",
            "translated_file": "Translated File",
            "select_file": "Select File",
            "output_rom": "💾 Translated ROM (Output)",
            "reinsertion_progress": "Reinsertion Progress",
            "reinsert": "Reinsert Translation",
            "theme": "🎨 Visual Theme",
            "ui_language": "🌐 Interface Language",
            "font_family": "🔤 Font Family",
            "log": "Operations Log",
            "restart": "Restart",
            "exit": "Exit",
            "developer": "Developed by: Celso (Solo Programmer)",
            "in_dev": "IN DEVELOPMENT",
            "file_to_translate": "📄 File to Translate (Optimized)",
            "no_file": "No file selected",
            "help_support": "🆘 Help & Support",
            "manual_guide": "📘 Professional User Guide:",
            "contact_support": "📧 Questions? Contact us:",
            "btn_stop": "Stop Translation",
            "btn_close": "Close",
            "roadmap_item": "Upcoming Consoles (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in development:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Other",
            "theme_black": "Black",
            "theme_gray": "Gray",
            "theme_white": "White",
            "gfx_toolbar": "Visualization Controls",
            "gfx_format": "Format:",
            "gfx_zoom": "Zoom:",
            "gfx_palette": "Palette:",
            "gfx_offset": "Address (Hex):",
            "gfx_tiles_per_row": "Width:",
            "gfx_num_tiles": "Num. Tiles:",
            "gfx_canvas": "Tile Viewer",
            "gfx_load_rom": "📂 Load a ROM in Tab 1 to view here",
            "gfx_navigation_hint": "Tip: Use keyboard arrows to navigate. Scroll to Zoom.",
            "gfx_analysis": "Analysis Tools",
            "gfx_editing": "Editing Tools",
            "gfx_btn_sniffer": "🔍 Detect Fonts",
            "gfx_btn_entropy": "[STATS] Compression Scanner",
            "gfx_btn_export": "📥 Export PNG",
            "gfx_btn_import": "📤 Import and Reinsert",
            "gfx_entropy_group": "Shannon Entropy Analysis",
            "gfx_entropy_click": "Click 'Entropy Scanner' to analyze...",
            "gfx_btn_prev": "◀ Previous Page",
            "gfx_btn_next": "Next Page ▶",
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
            "IMPORTANT: Don't add new colors! Use only existing colors from exported PNG.",
        },
        "es": {
            "title": "Extracción - Optimización - Traducción IA - Reinserción",
            "tab1": "🔍 1. Extracción",
            "tab2": "🎨 2. Laboratorio Gráfico (Beta)",
            "tab3": "🧠 3. Traducción",
            "tab4": "📥 4. Reinserción",
            "tab5": "⚙️ 5. Configuración",
            "platform": "Plataforma:",
            "rom_file": "Archivo ROM",
            "no_rom": "[WARN] Ninguna ROM seleccionada",
            "select_rom": "Seleccionar ROM",
            "extract_texts": "📄 Extraer Textos",
            "optimize_data": "🧹 Optimizar Datos",
            "extraction_progress": "Progreso de Extracción",
            "optimization_progress": "Progreso de Optimización",
            "waiting": "Esperando inicio...",
            "language_config": "🌍 Configuración de Idiomas",
            "source_language": "📖 Idioma de Origen (ROM)",
            "target_language": "🎯 Idioma de Destino",
            "translation_mode": "Modo de Traducción",
            "api_config": "Configuración de API",
            "api_key": "Clave API:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Usar caché de traducciones",
            "translation_progress": "Progreso de Traducción",
            "translate_ai": "🤖 Traducir con IA",
            "stop_translation": "🛑 Detener Traducción",
            "original_rom": "ROM Original",
            "translated_file": "Archivo Traducido",
            "select_file": "Seleccionar Archivo",
            "output_rom": "💾 ROM Traducida (Salida)",
            "reinsertion_progress": "Progreso de Reinserción",
            "reinsert": "Reinsertar Traducción",
            "theme": "🎨 Tema Visual",
            "ui_language": "🌐 Idioma de la Interfaz",
            "font_family": "🔤 Familia de Fuente",
            "log": "Registro de Operaciones",
            "restart": "Reiniciar",
            "exit": "Salir",
            "developer": "Desarrollado por: Celso (Programador Solo)",
            "in_dev": "EN DESARROLLO",
            "file_to_translate": "📄 Archivo para Traducir (Optimizado)",
            "no_file": "Ningún archivo seleccionado",
            "help_support": "🆘 Ayuda y Soporte",
            "manual_guide": "📘 Guía de Uso Profesional:",
            "contact_support": "📧 ¿Preguntas? Contáctenos:",
            "btn_stop": "Detener Traducción",
            "btn_close": "Cerrar",
            "roadmap_item": "Próximas Consolas (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Plataformas en desarrollo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Otro",
            "theme_black": "Negro",
            "theme_gray": "Gris",
            "theme_white": "Blanco",
        },
        "fr": {
            "title": "Extraction - Optimisation - Traduction IA - Réinsertion",
            "tab1": "🔍 1. Extraction",
            "tab2": "🎨 2. Labo Graphique (Beta)",
            "tab3": "🧠 3. Traduction",
            "tab4": "📥 4. Réinsertion",
            "tab5": "⚙️ 5. Paramètres",
            "platform": "Plateforme:",
            "rom_file": "Fichier ROM",
            "no_rom": "[WARN] Aucune ROM sélectionnée",
            "select_rom": "Sélectionner ROM",
            "extract_texts": "📄 Extraire Textes",
            "optimize_data": "🧹 Optimiser Données",
            "extraction_progress": "Progression de l'Extraction",
            "optimization_progress": "Progression de l'Optimisation",
            "waiting": "En attente...",
            "language_config": "🌍 Configuration des Langues",
            "source_language": "📖 Langue Source (ROM)",
            "target_language": "🎯 Langue Cible",
            "translation_mode": "Mode de Traduction",
            "api_config": "Configuration API",
            "api_key": "Clé API:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Utiliser le cache de traduction",
            "translation_progress": "Progression de la Traduction",
            "translate_ai": "🤖 Traduire avec IA",
            "stop_translation": "🛑 Arrêter Traduction",
            "original_rom": "ROM Originale",
            "translated_file": "Fichier Traduit",
            "select_file": "Sélectionner Fichier",
            "output_rom": "💾 ROM Traduite (Sortie)",
            "reinsertion_progress": "Progression de Réinsertion",
            "reinsert": "Réinsérer Traduction",
            "theme": "🎨 Thème Visuel",
            "ui_language": "🌐 Langue de l'Interface",
            "font_family": "🔤 Famille de Police",
            "log": "Journal des Opérations",
            "restart": "Redémarrer",
            "exit": "Quitter",
            "developer": "Développé par: Celso (Programmeur Solo)",
            "in_dev": "EN DÉVELOPPEMENT",
            "file_to_translate": "📄 Fichier à Traduire (Optimisé)",
            "no_file": "Aucun fichier sélectionné",
            "help_support": "🆘 Aide et Support",
            "manual_guide": "📘 Guide d'Utilisation Professionnel:",
            "contact_support": "📧 Questions? Contactez-nous:",
            "btn_stop": "Arrêter la Traduction",
            "btn_close": "Fermer",
            "roadmap_item": "Consoles à Venir (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Plateformes en développement:",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Autres",
            "theme_black": "Noir",
            "theme_gray": "Gris",
            "theme_white": "Blanc",
        },
        "de": {
            "title": "Extraktion - Optimierung - KI-Übersetzung - Wiedereinfügung",
            "tab1": "🔍 1. Extraktion",
            "tab2": "🎨 2. Grafiklabor (Beta)",
            "tab3": "🧠 3. Übersetzung",
            "tab4": "📥 4. Wiedereinfügung",
            "tab5": "⚙️ 5. Einstellungen",
            "platform": "Plattform:",
            "rom_file": "ROM-Datei",
            "no_rom": "[WARN] Keine ROM ausgewählt",
            "select_rom": "ROM auswählen",
            "extract_texts": "📄 Texte Extrahieren",
            "optimize_data": "🧹 Daten Optimieren",
            "extraction_progress": "Extraktionsfortschritt",
            "optimization_progress": "Optimierungsfortschritt",
            "waiting": "Warten...",
            "language_config": "🌍 Sprachkonfiguration",
            "source_language": "📖 Quellsprache (ROM)",
            "target_language": "🎯 Zielsprache",
            "translation_mode": "Übersetzungsmodus",
            "api_config": "API-Konfiguration",
            "api_key": "API-Schlüssel:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Übersetzungscache verwenden",
            "translation_progress": "Übersetzungsfortschritt",
            "translate_ai": "🤖 Mit KI Übersetzen",
            "stop_translation": "🛑 Übersetzung Stoppen",
            "original_rom": "Original-ROM",
            "translated_file": "Übersetzte Datei",
            "select_file": "Datei auswählen",
            "output_rom": "💾 Übersetzte ROM (Ausgabe)",
            "reinsertion_progress": "Wiedereinfügungsfortschritt",
            "reinsert": "Übersetzung Einfügen",
            "theme": "🎨 Visuelles Thema",
            "ui_language": "🌐 Oberflächensprache",
            "font_family": "🔤 Schriftfamilie",
            "log": "Operationsprotokoll",
            "restart": "Neustart",
            "exit": "Beenden",
            "developer": "Entwickelt von: Celso (Solo-Programmierer)",
            "in_dev": "IN ENTWICKLUNG",
            "file_to_translate": "📄 Zu übersetzende Datei (Optimiert)",
            "no_file": "Keine Datei ausgewählt",
            "help_support": "🆘 Hilfe und Support",
            "manual_guide": "📘 Professionelle Benutzeranleitung:",
            "contact_support": "📧 Fragen? Kontaktieren Sie uns:",
            "btn_stop": "Übersetzung Stoppen",
            "btn_close": "Schließen",
            "roadmap_item": "Kommende Konsolen (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Plattformen in Entwicklung:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Andet",
            "theme_black": "Schwarz",
            "theme_gray": "Grau",
            "theme_white": "Weiß",
        },
        "it": {
            "title": "Estrazione - Ottimizzazione - Traduzione IA - Reinserimento",
            "tab1": "🔍 1. Estrazione",
            "tab2": "🎨 2. Laboratorio Grafico (Beta)",
            "tab3": "🧠 3. Traduzione",
            "tab4": "📥 4. Reinserimento",
            "tab5": "⚙️ 5. Impostazioni",
            "platform": "Piattaforma:",
            "rom_file": "File ROM",
            "no_rom": "[WARN] Nessuna ROM selezionata",
            "select_rom": "Seleziona ROM",
            "extract_texts": "📄 Estrai Testi",
            "optimize_data": "🧹 Ottimizza Dati",
            "extraction_progress": "Progresso Estrazione",
            "optimization_progress": "Progresso Ottimizzazione",
            "waiting": "In attesa...",
            "language_config": "🌍 Configurazione Lingue",
            "source_language": "📖 Lingua Sorgente (ROM)",
            "target_language": "🎯 Lingua Destinazione",
            "translation_mode": "Modalità Traduzione",
            "api_config": "Configurazione API",
            "api_key": "Chiave API:",
            "workers": "Workers:",
            "timeout": "Timeout (s):",
            "use_cache": "Usa cache traduzioni",
            "translation_progress": "Progresso Traduzione",
            "translate_ai": "🤖 Traduci con IA",
            "stop_translation": "🛑 Ferma Traduzione",
            "original_rom": "ROM Originale",
            "translated_file": "File Tradotto",
            "select_file": "Seleziona File",
            "output_rom": "💾 ROM Tradotta (Output)",
            "reinsertion_progress": "Progresso Reinserimento",
            "reinsert": "Reinserisci Traduzione",
            "theme": "🎨 Tema Visivo",
            "ui_language": "🌐 Lingua Interfaccia",
            "font_family": "🔤 Famiglia di Caratteri",
            "log": "Registro Operazioni",
            "restart": "Riavvia",
            "exit": "Esci",
            "developer": "Sviluppato da: Celso (Programmatore Solo)",
            "in_dev": "IN SVILUPPO",
            "file_to_translate": "📄 File da Tradurre (Ottimizzato)",
            "no_file": "Nessun file selezionato",
            "help_support": "🆘 Aiuto e Supporto",
            "manual_guide": "📘 Guida Utente Professionale:",
            "contact_support": "📧 Domande? Contattaci:",
            "btn_stop": "Ferma Traduzione",
            "btn_close": "Chiudi",
            "roadmap_item": "Prossime Console (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Piattaforme in sviluppo:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "Altro",
            "theme_black": "Nero",
            "theme_gray": "Grigio",
            "theme_white": "Bianco",
        },
        "ja": {
            "title": "抽出 - 最適化 - AI翻訳 - 再挿入",
            "tab1": "🔍 1. 抽出",
            "tab2": "🎨 2. グラフィックラボ (Beta)",
            "tab3": "🧠 3. 翻訳",
            "tab4": "📥 4. 再挿入",
            "tab5": "⚙️ 5. 設定",
            "platform": "プラットフォーム:",
            "rom_file": "📂 ROMファイル",
            "no_rom": "[WARN] ROM未選択",
            "select_rom": "📂 ROM選択",
            "extract_texts": "📄 テキスト抽出",
            "optimize_data": "🧹 データ最適化",
            "extraction_progress": "抽出進行状況",
            "optimization_progress": "最適化進行状況",
            "waiting": "待機中...",
            "language_config": "🌍 言語設定",
            "source_language": "📖 ソース言語 (ROM)",
            "target_language": "🎯 ターゲット言語",
            "translation_mode": "翻訳モード",
            "api_config": "API設定",
            "api_key": "APIキー:",
            "workers": "ワーカー:",
            "timeout": "タイムアウト (秒):",
            "use_cache": "翻訳キャッシュを使用",
            "translation_progress": "翻訳進行状況",
            "translate_ai": "🤖 AIで翻訳",
            "stop_translation": "🛑 翻訳を停止",
            "original_rom": "📂 オリジナルROM",
            "translated_file": "📄 翻訳済みファイル",
            "select_file": "📄 ファイル選択",
            "output_rom": "💾 翻訳済みROM (出力)",
            "reinsertion_progress": "再挿入進行状況",
            "reinsert": "翻訳を再挿入",
            "theme": "🎨 ビジュアルテーマ",
            "ui_language": "🌐 インターフェース言語",
            "font_family": "🔤 フォントファミリー",
            "log": "操作ログ",
            "restart": "再起動",
            "exit": "終了",
            "developer": "開発者: Celso (ソロプログラマー)",
            "in_dev": "開発中",
            "file_to_translate": "📄 翻訳するファイル (最適化済み)",
            "no_file": "📄 ファイル未選択",
            "help_support": "🆘 ヘルプとサポート",
            "manual_guide": "📘 プロフェッショナルユーザーガイド:",
            "contact_support": "📧 ご質問？お問い合わせ:",
            "btn_stop": "翻訳を停止",
            "btn_close": "閉じる",
            "roadmap_item": "今後のコンソール (ロードマップ)...",
            "roadmap_title": "ロードマップ",
            "roadmap_desc": "開発中のプラットフォーム:",
            "roadmap_cat_playstation": "PlayStation",
            "roadmap_cat_nintendo_classic": "Nintendo Classic",
            "roadmap_cat_nintendo_portable": "Nintendo Portable",
            "roadmap_cat_sega": "Sega",
            "roadmap_cat_xbox": "Xbox",
            "roadmap_cat_other": "その他",
            "theme_black": "黒",
            "theme_gray": "灰色",
            "theme_white": "白",
        },
        "ko": {
            "title": "추출 - 최적화 - AI 번역 - 재삽입",
            "tab1": "🔍 1. 추출",
            "tab2": "🎨 2. 그래픽 연구소 (Beta)",
            "tab3": "🧠 3. 번역",
            "tab4": "📥 4. 재삽입",
            "tab5": "⚙️ 5. 설정",
            "platform": "플랫폼:",
            "rom_file": "ROM 파일",
            "no_rom": "[WARN] ROM 선택 안 됨",
            "select_rom": "ROM 선택",
            "extract_texts": "📄 텍스트 추출",
            "optimize_data": "🧹 데이터 최적화",
            "extraction_progress": "추출 진행률",
            "optimization_progress": "최적화 진행률",
            "waiting": "대기 중...",
            "language_config": "🌍 언어 설정",
            "source_language": "📖 소스 언어 (ROM)",
            "target_language": "🎯 대상 언어",
            "translation_mode": "번역 모드",
            "api_config": "API 구성",
            "api_key": "API 키:",
            "workers": "작업자:",
            "timeout": "타임아웃 (초):",
            "use_cache": "번역 캐시 사용",
            "translation_progress": "번역 진행률",
            "translate_ai": "🤖 AI로 번역",
            "stop_translation": "🛑 번역 중지",
            "original_rom": "원본 ROM",
            "translated_file": "번역된 파일",
            "select_file": "파일 선택",
            "output_rom": "💾 번역된 ROM (출력)",
            "reinsertion_progress": "재삽입 진행률",
            "reinsert": "번역 재삽입",
            "theme": "🎨 비주얼 테마",
            "ui_language": "🌐 인터페이스 언어",
            "font_family": "🔤 글꼴 패밀리",
            "log": "작업 로그",
            "restart": "재시작",
            "exit": "종료",
            "developer": "개발자: Celso (솔로 프로그래머)",
            "in_dev": "개발 중",
            "file_to_translate": "📄 번역할 파일 (최적화됨)",
            "no_file": "파일 선택 안 됨",
            "help_support": "🆘 도움말 및 지원",
            "manual_guide": "📘 전문 사용자 가이드:",
            "contact_support": "📧 질문이 있으신가요? 문의하기:",
            "btn_stop": "번역 중지",
            "btn_close": "닫기",
            "roadmap_item": "향후 콘솔 (로드맵)...",
            "roadmap_title": "로드맵",
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
            "theme_black": "검정",
            "theme_gray": "회색",
            "theme_white": "흰색",
        },
        "zh": {
            "title": "提取 - 优化 - AI翻译 - 重新插入",
            "tab1": "🔍 1. 提取",
            "tab2": "🎨 2. 图形实验室 (Beta)",
            "tab3": "🧠 3. 翻译",
            "tab4": "📥 4. 重新插入",
            "tab5": "⚙️ 5. 设置",
            "platform": "平台:",
            "rom_file": "ROM文件",
            "no_rom": "[WARN] 未选择ROM",
            "select_rom": "选择ROM",
            "extract_texts": "📄 提取文本",
            "optimize_data": "🧹 优化数据",
            "extraction_progress": "提取进度",
            "optimization_progress": "优化进度",
            "waiting": "等待中...",
            "language_config": "🌍 语言配置",
            "source_language": "📖 源语言 (ROM)",
            "target_language": "🎯 目标语言",
            "translation_mode": "翻译模式",
            "api_config": "API配置",
            "api_key": "API密钥:",
            "workers": "工作线程:",
            "timeout": "超时 (秒):",
            "use_cache": "使用翻译缓存",
            "translation_progress": "翻译进度",
            "translate_ai": "🤖 使用AI翻译",
            "stop_translation": "🛑 停止翻译",
            "original_rom": "原始ROM",
            "translated_file": "翻译文件",
            "select_file": "选择文件",
            "output_rom": "💾 翻译ROM (输出)",
            "reinsertion_progress": "重新插入进度",
            "reinsert": "重新插入翻译",
            "theme": "🎨 视觉主题",
            "ui_language": "🌐 界面语言",
            "font_family": "🔤 字体系列",
            "log": "操作日志",
            "restart": "重启",
            "exit": "退出",
            "developer": "开发者: Celso (独立程序员)",
            "in_dev": "开发中",
            "file_to_translate": "📄 要翻译的文件 (已优化)",
            "no_file": "未选择文件",
            "help_support": "🆘 帮助和支持",
            "manual_guide": "📘 专业用户指南:",
            "contact_support": "📧 有疑问？联系我们:",
            "btn_stop": "停止翻译",
            "btn_close": "关闭",
            "roadmap_item": "即将推出的游戏机 (路线图)...",
            "roadmap_title": "路线图",
            "roadmap_desc": "开发中的平台:",
            "theme_black": "黑色",
            "theme_gray": "灰色",
            "theme_white": "白色",
        },
        "ru": {
            "title": "Извлечение - Оптимизация - ИИ Перевод - Реинсерция",
            "tab1": "🔍 1. Извлечение",
            "tab2": "🎨 2. Графическая лаборатория (Beta)",
            "tab3": "🧠 3. Перевод",
            "tab4": "📥 4. Реинсерция",
            "tab5": "⚙️ 5. Настройки",
            "platform": "Платформа:",
            "rom_file": "ROM Файл",
            "no_rom": "[WARN] ROM не выбран",
            "select_rom": "Выбрать ROM",
            "extract_texts": "📄 Извлечь Тексты",
            "optimize_data": "🧹 Оптимизировать Данные",
            "extraction_progress": "Прогресс Извлечения",
            "optimization_progress": "Прогресс Оптимизации",
            "waiting": "Ожидание...",
            "language_config": "🌍 Настройка Языков",
            "source_language": "📖 Исходный Язык (ROM)",
            "target_language": "🎯 Целевой Язык",
            "translation_mode": "Режим Перевода",
            "api_config": "Настройка API",
            "api_key": "API Ключ:",
            "workers": "Воркеры:",
            "timeout": "Таймаут (сек):",
            "use_cache": "Использовать кэш переводов",
            "translation_progress": "Прогресс Перевода",
            "translate_ai": "🤖 Перевести с ИИ",
            "stop_translation": "🛑 Остановить Перевод",
            "original_rom": "Оригинальный ROM",
            "translated_file": "Переведенный Файл",
            "select_file": "Выбрать Файл",
            "output_rom": "💾 Переведенный ROM (Вывод)",
            "reinsertion_progress": "Прогресс Реинсерции",
            "reinsert": "Реинсертировать Перевод",
            "theme": "🎨 Визуальная Тема",
            "ui_language": "🌐 Язык Интерфейса",
            "font_family": "🔤 Семейство Шрифтов",
            "log": "Журнал Операций",
            "restart": "Перезапустить",
            "exit": "Выход",
            "developer": "Разработчик: Celso (Соло Программист)",
            "in_dev": "В РАЗРАБОТКЕ",
            "file_to_translate": "📄 Файл для Перевода (Оптимизирован)",
            "no_file": "Файл не выбран",
            "help_support": "🆘 Помощь и Поддержка",
            "manual_guide": "📘 Профессиональное Руководство:",
            "contact_support": "📧 Вопросы? Свяжитесь с нами:",
            "btn_stop": "Остановить Перевод",
            "btn_close": "Закрыть",
            "roadmap_item": "Предстоящие Консоли (Дорожная карта)...",
            "roadmap_title": "Дорожная карта",
            "roadmap_desc": "Платформы в разработке:",
            "theme_black": "Чёрный",
            "theme_gray": "Серый",
            "theme_white": "Белый",
        },
        "ar": {
            "title": "استخراج - تحسين - ترجمة الذكاء الاصطناعي - إعادة إدراج",
            "tab1": "🔍 1. استخراج",
            "tab2": "🎨 2. مختبر الرسوم (Beta)",
            "tab3": "🧠 3. ترجمة",
            "tab4": "📥 4. إعادة إدراج",
            "tab5": "⚙️ 5. إعدادات",
            "platform": "منصة:",
            "rom_file": "ملف ROM",
            "no_rom": "لم يتم تحديد ROM",
            "select_rom": "اختر ROM",
            "extract_texts": "استخراج النصوص",
            "optimize_data": "🧹 تحسين البيانات",
            "extraction_progress": "تقدم الاستخراج",
            "optimization_progress": "تقدم التحسين",
            "waiting": "في الانتظار...",
            "language_config": "🌍 تكوين اللغة",
            "source_language": "📖 اللغة المصدر (ROM)",
            "target_language": "🎯 اللغة المستهدفة",
            "translation_mode": "وضع الترجمة",
            "api_config": "تكوين API",
            "api_key": "مفتاح API:",
            "workers": "العمال:",
            "timeout": "المهلة (ثانية):",
            "use_cache": "استخدام ذاكرة التخزين المؤقت للترجمة",
            "translation_progress": "تقدم الترجمة",
            "translate_ai": "🤖 ترجمة بالذكاء الاصطناعي",
            "original_rom": "ROM الأصلي",
            "translated_file": "الملف المترجم",
            "select_file": "اختر ملف",
            "output_rom": "💾 ROM المترجم (الإخراج)",
            "reinsertion_progress": "تقدم إعادة الإدراج",
            "reinsert": "إعادة إدراج الترجمة",
            "theme": "🎨 السمة البصرية",
            "ui_language": "🌐 لغة الواجهة",
            "font_family": "🔤 عائلة الخط",
            "log": "سجل العمليات",
            "restart": "إعادة التشغيل",
            "exit": "خروج",
            "developer": "تطوير: Celso (مبرمج منفرد)",
            "in_dev": "قيد التطوير",
            "file_to_translate": "📄 ملف للترجمة (محسّن)",
            "no_file": "لم يتم تحديد ملف",
            "help_support": "🆘 المساعدة والدعم",
            "manual_guide": "📘 دليل المستخدم المحترف:",
            "contact_support": "📧 أسئلة؟ اتصل بنا:",
            "btn_stop": "إيقاف الترجمة",
            "btn_close": "إغلاق",
            "roadmap_item": "وحدات التحكم القادمة (خارطة الطريق)...",
            "roadmap_title": "خارطة الطريق",
            "roadmap_desc": "المنصات قيد التطوير:",
            "theme_black": "أسود",
            "theme_gray": "رمادي",
            "theme_white": "أبيض",
        },
        "hi": {
            "title": "निष्कर्षण - अनुकूलन - एआई अनुवाद - पुनः सम्मिलन",
            "tab1": "🔍 1. निष्कर्षण",
            "tab2": "🎨 2. ग्राफिक्स लैब (Beta)",
            "tab3": "🧠 3. अनुवाद",
            "tab4": "📥 4. पुनः सम्मिलन",
            "tab5": "⚙️ 5. सेटिंग्स",
            "platform": "मंच:",
            "rom_file": "ROM फ़ाइल",
            "no_rom": "कोई ROM चयनित नहीं",
            "select_rom": "ROM चुनें",
            "extract_texts": "पाठ निकालें",
            "optimize_data": "🧹 डेटा अनुकूलित करें",
            "extraction_progress": "निष्कर्षण प्रगति",
            "optimization_progress": "अनुकूलन प्रगति",
            "waiting": "प्रतीक्षा में...",
            "language_config": "🌍 भाषा कॉन्फ़िगरेशन",
            "source_language": "📖 स्रोत भाषा (ROM)",
            "target_language": "🎯 लक्ष्य भाषा",
            "translation_mode": "अनुवाद मोड",
            "api_config": "API कॉन्फ़िगरेशन",
            "api_key": "API कुंजी:",
            "workers": "वर्कर्स:",
            "timeout": "टाइमआउट (सेकंड):",
            "use_cache": "अनुवाद कैश का उपयोग करें",
            "translation_progress": "अनुवाद प्रगति",
            "translate_ai": "🤖 एआई से अनुवाद करें",
            "original_rom": "मूल ROM",
            "translated_file": "अनुवादित फ़ाइल",
            "select_file": "फ़ाइल चुनें",
            "output_rom": "💾 अनुवादित ROM (आउटपुट)",
            "reinsertion_progress": "पुनः सम्मिलन प्रगति",
            "reinsert": "अनुवाद पुनः सम्मिलित करें",
            "theme": "🎨 दृश्य थीम",
            "ui_language": "🌐 इंटरफ़ेस भाषा",
            "font_family": "🔤 फ़ॉन्ट परिवार",
            "log": "ऑपरेशन लॉग",
            "restart": "पुनः आरंभ करें",
            "exit": "बाहर निकलें",
            "developer": "विकसित: Celso (एकल प्रोग्रामर)",
            "in_dev": "विकास में",
            "file_to_translate": "📄 अनुवाद करने के लिए फ़ाइल (अनुकूलित)",
            "no_file": "कोई फ़ाइल चयनित नहीं",
            "help_support": "🆘 सहायता और समर्थन",
            "manual_guide": "📘 पेशेवर उपयोगकर्ता गाइड:",
            "contact_support": "📧 सवाल? हमसे संपर्क करें:",
            "btn_stop": "अनुवाद रोकें",
            "btn_close": "बंद करें",
            "roadmap_item": "आगामी कंसोल (रोडमैप)...",
            "roadmap_title": "रोडमैप",
            "roadmap_desc": "विकास में प्लेटफ़ॉर्म:",
            "theme_black": "काला",
            "theme_gray": "स्लेटी",
            "theme_white": "सफेद",
        },
        "tr": {
            "title": "Çıkarma - Optimizasyon - Yapay Zeka Çevirisi - Yeniden Ekleme",
            "tab1": "🔍 1. Çıkarma",
            "tab2": "🎨 2. Grafik Laboratuvarı (Beta)",
            "tab3": "🧠 3. Çeviri",
            "tab4": "📥 4. Yeniden Ekleme",
            "tab5": "⚙️ 5. Ayarlar",
            "platform": "Platform:",
            "rom_file": "ROM Dosyası",
            "no_rom": "ROM seçilmedi",
            "select_rom": "ROM Seç",
            "extract_texts": "METİNLERİ ÇIKAR",
            "optimize_data": "🧹 VERİLERİ OPTİMİZE ET",
            "extraction_progress": "Çıkarma İlerlemesi",
            "optimization_progress": "Optimizasyon İlerlemesi",
            "waiting": "Bekleniyor...",
            "language_config": "🌍 Dil Yapılandırması",
            "source_language": "📖 Kaynak Dil (ROM)",
            "target_language": "🎯 Hedef Dil",
            "translation_mode": "Çeviri Modu",
            "api_config": "API Yapılandırması",
            "api_key": "API Anahtarı:",
            "workers": "İşçiler:",
            "timeout": "Zaman Aşımı (sn):",
            "use_cache": "Çeviri önbelleğini kullan",
            "translation_progress": "Çeviri İlerlemesi",
            "translate_ai": "🤖 YAPAY ZEKA İLE ÇEVİR",
            "original_rom": "Orijinal ROM",
            "translated_file": "Çevrilmiş Dosya",
            "select_file": "Dosya Seç",
            "output_rom": "💾 Çevrilmiş ROM (Çıktı)",
            "reinsertion_progress": "Yeniden Ekleme İlerlemesi",
            "reinsert": "ÇEVİRİYİ YENİDEN EKLE",
            "theme": "🎨 Görsel Tema",
            "ui_language": "🌐 Arayüz Dili",
            "font_family": "🔤 Yazı Tipi Ailesi",
            "log": "İşlem Günlüğü",
            "restart": "YENİDEN BAŞLAT",
            "exit": "ÇIKIŞ",
            "developer": "Geliştirici: Celso (Solo Programcı)",
            "in_dev": "GELİŞTİRMEDE",
            "file_to_translate": "📄 Çevrilecek Dosya (Optimize Edilmiş)",
            "no_file": "Dosya seçilmedi",
            "help_support": "🆘 Yardım ve Destek",
            "manual_guide": "📘 Profesyonel Kullanıcı Kılavuzu:",
            "contact_support": "📧 Sorularınız mı var? Bize ulaşın:",
            "btn_stop": "ÇEVİRİYİ DURDUR",
            "btn_close": "KAPAT",
            "roadmap_item": "Yaklaşan Konsollar (Yol Haritası)...",
            "roadmap_title": "Yol Haritası",
            "roadmap_desc": "Geliştirme aşamasındaki platformlar:",
            "theme_black": "Siyah",
            "theme_gray": "Gri",
            "theme_white": "Beyaz",
        },
        "pl": {
            "title": "Ekstrakcja - Optymalizacja - Tłumaczenie AI - Reinsercja",
            "tab1": "🔍 1. Ekstrakcja",
            "tab2": "🎨 2. Laboratorium Graficzne (Beta)",
            "tab3": "🧠 3. Tłumaczenie",
            "tab4": "📥 4. Reinsercja",
            "tab5": "⚙️ 5. Ustawienia",
            "platform": "Platforma:",
            "rom_file": "Plik ROM",
            "no_rom": "Nie wybrano ROM",
            "select_rom": "Wybierz ROM",
            "extract_texts": "WYODRĘBNIJ TEKSTY",
            "optimize_data": "🧹 OPTYMALIZUJ DANE",
            "extraction_progress": "Postęp Ekstrakcji",
            "optimization_progress": "Postęp Optymalizacji",
            "waiting": "Oczekiwanie...",
            "language_config": "🌍 Konfiguracja Języka",
            "source_language": "📖 Język Źródłowy (ROM)",
            "target_language": "🎯 Język Docelowy",
            "translation_mode": "Tryb Tłumaczenia",
            "api_config": "Konfiguracja API",
            "api_key": "Klucz API:",
            "workers": "Pracownicy:",
            "timeout": "Limit czasu (s):",
            "use_cache": "Użyj pamięci podręcznej tłumaczeń",
            "translation_progress": "Postęp Tłumaczenia",
            "translate_ai": "🤖 TŁUMACZ Z AI",
            "original_rom": "Oryginalny ROM",
            "translated_file": "Przetłumaczony Plik",
            "select_file": "Wybierz Plik",
            "output_rom": "💾 Przetłumaczony ROM (Wyjście)",
            "reinsertion_progress": "Postęp Reinsercji",
            "reinsert": "WSTAW TŁUMACZENIE",
            "theme": "🎨 Motyw Wizualny",
            "ui_language": "🌐 Język Interfejsu",
            "font_family": "🔤 Rodzina Czcionek",
            "log": "Dziennik Operacji",
            "restart": "RESTART",
            "exit": "WYJŚCIE",
            "developer": "Opracowane przez: Celso (Programista Solo)",
            "in_dev": "W ROZWOJU",
            "file_to_translate": "📄 Plik do Tłumaczenia (Zoptymalizowany)",
            "no_file": "Nie wybrano pliku",
            "help_support": "🆘 Pomoc i Wsparcie",
            "manual_guide": "📘 Profesjonalny Przewodnik:",
            "contact_support": "📧 Pytania? Skontaktuj się z nami:",
            "btn_stop": "ZATRZYMAJ TŁUMACZENIE",
            "btn_close": "ZAMKNIJ",
            "roadmap_item": "Nadchodzące Konsole (Mapa drogowa)...",
            "roadmap_title": "Mapa drogowa",
            "roadmap_desc": "Platformy w rozwoju:",
            "theme_black": "Czarny",
            "theme_gray": "Szary",
            "theme_white": "Biały",
        },
        "nl": {
            "title": "Extractie - Optimalisatie - AI Vertaling - Herinvoer",
            "tab1": "🔍 1. Extractie",
            "tab2": "🎨 2. Grafisch Lab (Beta)",
            "tab3": "🧠 3. Vertaling",
            "tab4": "📥 4. Herinvoer",
            "tab5": "⚙️ 5. Instellingen",
            "platform": "Platform:",
            "rom_file": "ROM Bestand",
            "no_rom": "Geen ROM geselecteerd",
            "select_rom": "Selecteer ROM",
            "extract_texts": "TEKSTEN EXTRAHEREN",
            "optimize_data": "🧹 DATA OPTIMALISEREN",
            "extraction_progress": "Extractie Voortgang",
            "optimization_progress": "Optimalisatie Voortgang",
            "waiting": "Wachten...",
            "language_config": "🌍 Taalconfiguratie",
            "source_language": "📖 Brontaal (ROM)",
            "target_language": "🎯 Doeltaal",
            "translation_mode": "Vertaalmodus",
            "api_config": "API Configuratie",
            "api_key": "API Sleutel:",
            "workers": "Workers:",
            "timeout": "Time-out (s):",
            "use_cache": "Gebruik vertaalcache",
            "translation_progress": "Vertaalvoortgang",
            "translate_ai": "🤖 VERTALEN MET AI",
            "original_rom": "Originele ROM",
            "translated_file": "Vertaald Bestand",
            "select_file": "Selecteer Bestand",
            "output_rom": "💾 Vertaalde ROM (Uitvoer)",
            "reinsertion_progress": "Herinvoer Voortgang",
            "reinsert": "VERTALING HERINVOEREN",
            "theme": "🎨 Visueel Thema",
            "ui_language": "🌐 Interface Taal",
            "font_family": "🔤 Lettertypefamilie",
            "log": "Operatielogboek",
            "restart": "HERSTARTEN",
            "exit": "AFSLUITEN",
            "developer": "Ontwikkeld door: Celso (Solo Programmeur)",
            "in_dev": "IN ONTWIKKELING",
            "file_to_translate": "📄 Te vertalen bestand (Geoptimaliseerd)",
            "no_file": "Geen bestand geselecteerd",
            "help_support": "🆘 Hulp en Ondersteuning",
            "manual_guide": "📘 Professionele Gebruikersgids:",
            "contact_support": "📧 Vragen? Neem contact op:",
            "btn_stop": "VERTALING STOPPEN",
            "btn_close": "SLUITEN",
            "roadmap_item": "Komende Consoles (Roadmap)...",
            "roadmap_title": "Roadmap",
            "roadmap_desc": "Platforms in ontwikkeling:",
            "theme_black": "Zwart",
            "theme_gray": "Grijs",
            "theme_white": "Wit",
        },
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
        try:
            # Força Fusion antes de aplicar o stylesheet
            app.setStyle("Fusion")
        except Exception:
            pass

        # Scrollbar + controles globais (cinza/preto)
        border_color = _get_theme_border_color(theme_name, theme["window"])
        base_window = QColor(theme["window"])
        base_button = QColor(theme["button"])
        base_text = QColor(theme["text"])
        text_muted = base_text.darker(140).name()
        text_disabled = "#9A9A9A"
        btn_bg = theme["button"]
        btn_hover = (
            base_button.lighter(110).name()
            if theme_name != "Preto (Black)"
            else theme["button"]
        )
        btn_pressed = (
            base_button.darker(110).name()
            if theme_name != "Preto (Black)"
            else theme["button"]
        )
        btn_border = (
            border_color
            if theme_name == "Preto (Black)"
            else base_button.darker(130).name()
        )
        input_border = border_color
        disabled_bg = (
            base_window.darker(110).name()
            if theme_name != "Preto (Black)"
            else theme["window"]
        )
        disabled_border = border_color
        panel_bg = "#3A3A3A" if theme_name == "Cinza (Gray)" else theme["button"]
        scroll_handle = base_button.lighter(140).name()
        if QColor(scroll_handle).lightness() < 40:
            scroll_handle = "#6B6B6B"
        scroll_handle_border = QColor(scroll_handle).darker(120).name()
        progress_text = base_text.darker(150).name()
        scrollbar_style = """
        QMainWindow, QDialog, QMessageBox {{
            background-color: {window};
            color: {text};
        }}
        QWidget {{
            background-color: {window};
            color: {text};
        }}
        QLabel, QCheckBox, QGroupBox, QTabBar::tab, QMenuBar, QMenu {{
            color: {text};
        }}
        QLabel:disabled, QCheckBox:disabled, QGroupBox:disabled, QTabBar::tab:disabled {{
            color: {text_disabled};
        }}
        QMenuBar {{
            background-color: {window};
            border-bottom: 1px solid {border};
        }}
        QMenuBar::item:selected {{
            background-color: {btn_bg};
        }}
        QFrame {{
            background-color: {window};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QScrollArea {{
            background-color: {window};
        }}
        QAbstractScrollArea::viewport {{
            background-color: {window};
        }}
        QTabWidget::pane {{
            background-color: {window};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QTextEdit, QPlainTextEdit {{
            background-color: {button};
            color: {text};
            border: 1px solid {input_border};
        }}
        QMenu {{
            background-color: {panel_bg};
            color: {text};
            border: 1px solid {border};
        }}
        QMenu::item:disabled {{
            color: {text_disabled};
        }}
        QMenuBar::item:disabled {{
            color: {text_disabled};
        }}
        QMenu::item:selected {{
            background-color: {button};
            color: {text};
        }}
        QGroupBox {{
            background-color: {window};
            border: 1px solid {border};
            border-radius: 8px;
            margin-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: {text};
        }}
        QPushButton {{
            background-color: {btn_bg};
            border: 1px solid {btn_border};
            color: {text_muted};
            font-weight: 300;
            font-size: 10pt;
        }}
        QPushButton:hover {{
            background-color: {btn_hover};
            border: 1px solid {btn_border};
        }}
        QPushButton:pressed {{
            background-color: {btn_pressed};
            border: 1px solid {btn_border};
        }}
        QPushButton:disabled {{
            background-color: {disabled_bg};
            border: 1px solid {disabled_border};
            color: {text_disabled};
        }}
        QComboBox {{
            background: {button};
            border: 1px solid {input_border};
            border-radius: 6px;
            padding: 6px 28px 6px 10px;
            color: {text};
        }}
        QComboBox:focus {{
            border: 2px solid {accent};
            background: {button};
        }}
        QComboBox:hover {{
            border: 1px solid {accent};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 26px;
            background: {button};
            border-left: 1px solid {border};
        }}
        QComboBox::down-arrow {{
            width: 10px;
            height: 10px;
        }}
        QComboBox QAbstractItemView {{
            background: {panel_bg};
            color: {text};
            selection-background-color: {accent};
            border: 1px solid {border};
        }}
        QComboBox QAbstractItemView::item:disabled {{
            color: #8A8A8A;
        }}
        #logText {{
            font-family: "Consolas";
        }}
        QLabel[class="proBadge"] {{
            color: #C8A951;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-right: 10px;
        }}
        QLineEdit {{
            background-color: {button};
            color: {text};
            border: 1px solid {input_border};
            padding: 4px 8px;
        }}
        QLineEdit:hover {{
            border: 1px solid {accent};
        }}
        QLineEdit:focus {{
            border: 1px solid {accent};
        }}
        QAbstractSpinBox:hover {{
            border: 1px solid {accent};
        }}
        QAbstractSpinBox:focus {{
            border: 1px solid {accent};
        }}
        QLineEdit:disabled {{
            color: {text_disabled};
            background-color: {button};
            border: 1px solid {disabled_border};
        }}
        QAbstractSpinBox:disabled, QComboBox:disabled {{
            color: {text_disabled};
            background-color: {button};
            border: 1px solid {disabled_border};
        }}
        QLineEdit::placeholder {{
            color: {text_muted};
        }}
        QListView, QTreeView, QTableView {{
            background-color: {window};
            color: {text};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QScrollBar:vertical {{
            background: {window};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {scroll_handle};
            border: 1px solid {scroll_handle_border};
            min-height: 28px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {accent};
            border: 1px solid {accent};
        }}
        QScrollBar::add-line:vertical {{
            background: transparent;
            height: 0px;
            subcontrol-position: bottom;
            subcontrol-origin: margin;
            border: none;
        }}
        QScrollBar::sub-line:vertical {{
            background: transparent;
            height: 0px;
            subcontrol-position: top;
            subcontrol-origin: margin;
            border: none;
        }}
        QScrollBar::up-arrow:vertical {{
            width: 0px;
            height: 0px;
            border: none;
        }}
        QScrollBar::down-arrow:vertical {{
            width: 0px;
            height: 0px;
            border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: {window};
        }}

        QScrollBar:horizontal {{
            background: {window};
            height: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {scroll_handle};
            border: 1px solid {scroll_handle_border};
            min-width: 28px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {accent};
            border: 1px solid {accent};
        }}
        QScrollBar::add-line:horizontal {{
            background: transparent;
            width: 0px;
            subcontrol-position: right;
            subcontrol-origin: margin;
            border: none;
        }}
        QScrollBar::sub-line:horizontal {{
            background: transparent;
            width: 0px;
            subcontrol-position: left;
            subcontrol-origin: margin;
            border: none;
        }}
        QScrollBar::left-arrow:horizontal {{
            width: 0px;
            height: 0px;
            border: none;
        }}
        QScrollBar::right-arrow:horizontal {{
            width: 0px;
            height: 0px;
            border: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: {window};
        }}
        QPushButton[class="primary"] {{
            background: {accent};
            border: 1px solid {accent};
            color: #FFFFFF;
            font-weight: 600;
        }}
        QPushButton[class="primary"]:hover {{
            background: {accent};
        }}
        QPushButton[class="primary"]:pressed {{
            background: {accent};
            border: 1px solid {accent};
        }}
        QPushButton[class="primaryOutline"] {{
            background: {button};
            border: 2px solid {accent};
            color: {text};
            font-weight: 600;
        }}
        QPushButton[class="primaryOutline"]:hover {{
            background: {window};
        }}
        QPushButton[class="primaryOutline"]:pressed {{
            background: {window};
        }}
        QPushButton[class="danger"] {{
            background: #EF4444;
            border: 1px solid #C83737;
            color: #FFFFFF;
            font-weight: 600;
        }}
        QPushButton[class="danger"]:hover {{
            background: #E13A3A;
        }}
        QPushButton[class="danger"]:pressed {{
            background: #C83737;
            border: 1px solid #C83737;
        }}
        QPushButton[class="dangerOutline"] {{
            background: {button};
            border: 2px solid #EF4444;
            color: #FFECEC;
            font-weight: 600;
        }}
        QPushButton[class="dangerOutline"]:hover {{
            background: {window};
        }}
        QPushButton[class="primary"]:disabled,
        QPushButton[class="danger"]:disabled,
        QPushButton[class="primaryOutline"]:disabled,
        QPushButton[class="dangerOutline"]:disabled {{
            background: {disabled_bg};
            border: 1px solid {disabled_border};
            color: {text_disabled};
        }}
        QTabBar::tab:selected {{
            border-bottom: 2px solid {accent};
            color: #EDEDED;
        }}
        QTabBar::tab:hover {{
            color: #EDEDED;
        }}
        QProgressBar {{
            border: 1px solid {border};
            border-radius: 7px;
            background: {button};
            text-align: center;
            color: {progress_text};
        }}
        QProgressBar::chunk {{
            background: {accent};
            border-radius: 7px;
        }}
        QToolButton {{
            min-width: 28px;
            min-height: 28px;
            max-width: 28px;
            max-height: 28px;
            padding: 0px;
        }}
        QToolButton:hover {{
            background: {button};
            border-radius: 6px;
        }}
        #logText {{
            font-family: "Consolas";
        }}
        QWidget {{
            font-family: "Segoe UI", "Malgun Gothic", "Yu Gothic UI", "Microsoft JhengHei UI", sans-serif;
        }}
        """.format(
            button=theme["button"],
            text=theme["text"],
            window=theme["window"],
            accent=theme["accent"],
            border=border_color,
            btn_bg=btn_bg,
            btn_hover=btn_hover,
            btn_pressed=btn_pressed,
            btn_border=btn_border,
            input_border=input_border,
            disabled_bg=disabled_bg,
            disabled_border=disabled_border,
            text_muted=text_muted,
            text_disabled=text_disabled,
            panel_bg=panel_bg,
            scroll_handle=scroll_handle,
            scroll_handle_border=scroll_handle_border,
            progress_text=progress_text,
        )
        try:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(theme["window"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(theme["button"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["window"]))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme["window"]))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme["text"]))
            palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(theme["button"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            app.setPalette(palette)
        except Exception:
            pass
        def _clear_local_color_qss(root):
            import re

            color_re = re.compile(
                r"(?i)(background(?:-color)?|selection-background-color|border(?!-radius)\b|border-(?:top|bottom|left|right))\s*:[^;{}]*;?"
            )
            for w in [root] + root.findChildren(QWidget):
                if isinstance(w, (QAbstractButton, QMenuBar)):
                    continue
                ss = w.styleSheet() or ""
                if not ss.strip():
                    continue
                cleaned = color_re.sub("", ss)
                cleaned = re.sub(r";\s*;", ";", cleaned).strip()
                if cleaned != ss.strip():
                    w.setStyleSheet(cleaned)

        app.setStyleSheet(scrollbar_style)
        try:
            for w in app.topLevelWidgets():
                w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                try:
                    if hasattr(w, "centralWidget"):
                        cw = w.centralWidget()
                        if cw:
                            cw.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                except Exception:
                    pass
                try:
                    for scroll in w.findChildren(QAbstractScrollArea):
                        viewport = scroll.viewport()
                        if viewport:
                            viewport.setAttribute(
                                Qt.WidgetAttribute.WA_StyledBackground, True
                            )
                except Exception:
                    pass
                try:
                    for tab in w.findChildren(QTabWidget):
                        for i in range(tab.count()):
                            page = tab.widget(i)
                            if page:
                                page.setAttribute(
                                    Qt.WidgetAttribute.WA_StyledBackground, True
                                )
                except Exception:
                    pass
                _clear_local_color_qss(w)
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()
        except Exception:
            pass


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
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""


# ================================================================================
# RTCE Process Selection Dialog
# ================================================================================
class RTCEProcessDialog(QDialog):
    """Diálogo para selecionar processo do emulador e configurar captura."""

    def __init__(self, platform: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.setWindowTitle(self.tr("rtce_window_title"))
        self.setMinimumSize(1400, 900)
        self.selected_process = None
        self.duration = 300
        self.init_ui()

    def tr(self, key: str) -> str:
        parent = self.parent()
        if parent and hasattr(parent, "tr"):
            return parent.tr(key)
        translations = ProjectConfig.load_translations("en")
        return translations.get(key, key)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info_label = QLabel(self.tr("rtce_info").format(platform=self.platform))
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "padding: 10px; background-color: #2d2d2d; border-radius: 6px;"
        )
        layout.addWidget(info_label)

        # Lista de processos
        process_group = QGroupBox(self.tr("rtce_process_group"))
        process_layout = QVBoxLayout()

        # Detectar processos
        self.process_list = QComboBox()
        self.process_list.setMinimumHeight(35)

        # Processos comuns por plataforma
        emulators_map = {
            "SNES": [
                "snes9x-x64.exe",
                "snes9x.exe",
                "bsnes.exe",
                "higan.exe",
                "zsnes.exe",
            ],
            "NES": ["fceux.exe", "nestopia.exe", "mesen.exe"],
            "N64": ["project64.exe", "mupen64plus.exe", "m64p.exe"],
            "GBA": ["visualboyadvance.exe", "mgba.exe", "vba-m.exe"],
            "NDS": ["desmume.exe", "melonds.exe", "no$gba.exe"],
            "GENESIS": ["kega-fusion.exe", "gens.exe", "blastem.exe"],
            "PS1": ["epsxe.exe", "pcsxr.exe", "duckstation.exe", "mednafen.exe"],
            "PS2": ["pcsx2.exe", "pcsx2-qt.exe"],
            "PC_WINDOWS": ["*.exe"],
        }

        expected_emulators = emulators_map.get(self.platform, [])

        # Listar processos rodando
        if not PSUTIL_AVAILABLE:
            self.process_list.addItem(self.tr("rtce_psutil_missing"), None)
        else:
            try:
                running_processes = []
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        proc_name = proc.info["name"].lower()
                        # Filtrar apenas emuladores esperados
                        if any(
                            emu.lower().replace("*", "") in proc_name
                            for emu in expected_emulators
                        ):
                            running_processes.append(
                                (proc.info["name"], proc.info["pid"])
                            )
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                    ):
                        continue

                if running_processes:
                    for proc_name, pid in running_processes:
                        self.process_list.addItem(f"{proc_name} (PID: {pid})", proc_name)
                else:
                    self.process_list.addItem(self.tr("rtce_no_emulator"), None)
            except Exception:
                self.process_list.addItem(
                    self.tr("rtce_process_fail"),
                    None,
                )

        # Opção manual
        self.process_list.addItem(self.tr("rtce_manual_entry"), "manual")

        process_layout.addWidget(self.process_list)

        # Campo manual
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText(self.tr("rtce_manual_placeholder"))
        self.manual_input.setVisible(False)
        self.manual_input.setMinimumHeight(30)
        process_layout.addWidget(self.manual_input)

        self.process_list.currentIndexChanged.connect(self.on_process_changed)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # Configurações
        config_group = QGroupBox(self.tr("rtce_config_group"))
        config_layout = QFormLayout()

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(30, 3600)
        self.duration_spin.setValue(300)
        self.duration_spin.setSuffix(self.tr("rtce_seconds_suffix"))
        self.duration_spin.setMinimumHeight(30)
        config_layout.addRow(self.tr("rtce_duration_label"), self.duration_spin)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Dicas
        tips_label = QLabel(self.tr("rtce_tips"))
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet(
            "padding: 10px; background-color: #1a3a1a; border-radius: 6px; color: #aaffaa;"
        )
        layout.addWidget(tips_label)

        # Botões
        button_layout = QHBoxLayout()
        neutral_button_style = self._get_neutral_button_style()
        cancel_btn = QPushButton(self.tr("btn_cancel"))
        cancel_btn.setMinimumHeight(35)
        cancel_btn.clicked.connect(self.reject)

        start_btn = QPushButton(self.tr("rtce_start_capture"))
        start_btn.setMinimumHeight(35)
        start_btn.setStyleSheet(neutral_button_style)
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

    def __init__(self, platform_name, process_name=None, duration_sec=300, parent=None):
        # CORREÇÃO: Isso evita o erro de "unexpected type 'str'"
        super().__init__(parent)
        self.platform_name = platform_name
        self.process_name = process_name
        self.duration_sec = max(30, int(duration_sec or 0))
        self._is_running = True
        self._all_texts = []

    def run(self):
        try:
            import time
            from rtce_core.rtce_engine import RTCEEngine

            # Inicializa o motor v 6.0
            engine = RTCEEngine(platform=self.platform_name, process_name=self.process_name)

            if not engine.attach_to_process(self.process_name):
                self.log_signal.emit(
                    "[ERROR] [RTCE] Emulador não detectado. Abra o jogo primeiro!"
                )
                return

            self.log_signal.emit(
                f"[OK] [RTCE] Conectado ao processo! Capturando {self.platform_name}..."
            )

            start_ts = time.time()
            while self._is_running and (time.time() - start_ts) < self.duration_sec:
                results = engine.scan_once(deduplicate=True)
                if results:
                    for r in results:
                        # Filtro de Perfeccionista: Mostra endereço e texto
                        msg = f"[0x{r.offset}] {r.text}"
                        self.text_found_signal.emit(msg)
                        self._all_texts.append(
                            {
                                "text": r.text,
                                "offset": r.offset,
                                "confidence": r.confidence,
                                "text_type": r.text_type,
                            }
                        )

                self.msleep(1000)  # Verifica a cada 1 segundo

            engine.detach_from_process()
            self.finished_signal.emit(self._all_texts)

        except Exception as e:
            self.log_signal.emit(f"[ERROR] Erro no Motor RTCE: {_sanitize_error(e)}")
            self.error_signal.emit(_sanitize_error(e))

    def stop(self):
        self._is_running = False


class MainWindow(QMainWindow):
    def clear_translation_cache(self):
        """Limpa o cache de traduções para forçar retradução."""
        from pathlib import Path

        # Cache fica na pasta do framework
        framework_dir = Path(__file__).parent.parent

        # Arquivos de cache possíveis
        cache_names = [
            "cache_traducoes.json",
            "translation_cache.json",
            "cache_translations.json",
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
            QMessageBox.information(
                self, self.tr("cache_title"), self.tr("cache_none_found")
            )
            return

        # Mostra arquivos encontrados
        files_info = "\n".join(
            [f"• {f.name} ({f.stat().st_size // 1024} KB)" for f in cache_files]
        )

        reply = QMessageBox.question(
            self,
            self.tr("cache_clear_title"),
            self.tr("cache_clear_confirm").format(
                count=len(cache_files), files=files_info
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                for f in cache_files:
                    f.unlink()
                self.log(f"🗑️ Cache limpo: {len(cache_files)} arquivo(s) removido(s)")
                QMessageBox.information(
                    self,
                    self.tr("cache_title"),
                    self.tr("cache_cleared_message").format(count=len(cache_files)),
                )
            except Exception as e:
                self.log(f"[ERROR] Erro ao limpar cache: {_sanitize_error(e)}")
                QMessageBox.warning(
                    self,
                    self.tr("dialog_title_error"),
                    self.tr("cache_clear_error").format(error=e),
                )

    # --- 2. INICIALIZAÇÃO CORRIGIDA ---
    def __init__(self):
        super().__init__()

        self._startup = True
        startup_config = self._read_startup_config()
        self._config_missing = not ProjectConfig.CONFIG_FILE.exists()

        # Variáveis de Estado
        self.original_rom_path = None
        self.extracted_file = None
        self.optimized_file = None
        self.translated_file = None
        self.detected_platform_code = None  # ADICIONE ESTA LINHA
        self.current_rom_crc32 = None
        self.current_rom_size = None
        self.last_rom_dir = str(ProjectConfig.ROMS_DIR)
        self.last_text_dir = str(ProjectConfig.ROMS_DIR)
        self.current_output_dir = None
        self.onboarding_shown = False
        self.max_extraction_mode = False
        self.max_extraction_locked = True
        self.beginner_mode = True
        self.graphics_lab_tab = None
        self.developer_mode = bool(startup_config.get("developer_mode", False))
        self.auto_graphics_pipeline = bool(startup_config.get("auto_graphics_pipeline", True))
        self.gfx_needs_review = 0

        # RTCE State (Motor v 6.0)
        self.rtce_thread = None

        self.current_theme = "Preto (Black)"
        self.current_ui_lang = self._resolve_initial_ui_language(startup_config)
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

        # [OK] CONFIGURAÇÕES DO OTIMIZADOR (Expert Mode)
        self.optimizer_config = {
            "preserve_commands": True,
            "replace_symbol": "@",
            "replace_with": " ",
            "remove_overlaps": True,
        }

        self.init_ui()
        self.apply_layout_direction()
        self.load_config(silent=True)
        if self._config_missing:
            self.save_config()
        self._apply_beginner_mode()
        self._startup = False
        self.log(f"[CFG] config_path={ProjectConfig.CONFIG_FILE.name}")
        self.log(f"[LANG] UI language: {self._format_lang_for_log()}")
        QApplication.instance().installEventFilter(self)
        self._apply_pointing_cursor_everywhere()
        try:
            self._clear_local_color_qss(self)
        except Exception:
            pass
        QTimer.singleShot(200, self._show_startup_help_and_tour)

    def _show_startup_help_every_time(self):
        self.show_quick_help_dialog()

    def _show_startup_help_and_tour(self):
        self._show_startup_help_every_time()
        self._maybe_start_guided_tour()

    def _maybe_start_guided_tour(self):
        """Inicia o tour apenas quando o modo passo a passo estiver ativo."""
        try:
            if hasattr(self, "beginner_mode_cb") and self.beginner_mode_cb:
                if not self.beginner_mode_cb.isChecked():
                    return
            elif not getattr(self, "beginner_mode", False):
                return
        except Exception:
            pass
        self.start_guided_tour()

    def _apply_pointing_cursor_everywhere(self):
        # Botões
        for w in self.findChildren(QPushButton):
            w.setCursor(Qt.CursorShape.PointingHandCursor)
        for w in self.findChildren(QToolButton):
            w.setCursor(Qt.CursorShape.PointingHandCursor)

        # Checkbox
        for w in self.findChildren(QCheckBox):
            w.setCursor(Qt.CursorShape.PointingHandCursor)

        # Combobox + popup
        for combo in self.findChildren(QComboBox):
            combo.setCursor(Qt.CursorShape.PointingHandCursor)
            try:
                combo.view().setCursor(Qt.CursorShape.PointingHandCursor)
                combo.view().viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass

        # Abas
        try:
            if hasattr(self, "tabs") and self.tabs:
                self.tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass

        # Menus
        for menu in self.findChildren(QMenu):
            menu.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            mb = self.menuBar()
            if mb:
                self._apply_menu_action_cursors(mb)
        except Exception:
            pass

    def _apply_menu_action_cursors(self, menu_obj):
        """Aplica cursor de mão em menus e ações (quando suportado)."""
        if not menu_obj:
            return
        try:
            menu_obj.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass
        try:
            actions = menu_obj.actions()
        except Exception:
            return
        for action in actions:
            try:
                if hasattr(action, "setCursor"):
                    action.setCursor(Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass
            try:
                sub = action.menu()
            except Exception:
                sub = None
            if sub:
                self._apply_menu_action_cursors(sub)

    def _apply_button_class(self, btn: QAbstractButton, class_name: str) -> None:
        """Aplica classe de estilo no botão e força repintura."""
        if not btn:
            return
        btn.setProperty("class", class_name)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()

    def _clear_local_color_qss(self, root: QWidget):
        import re

        color_re = re.compile(
            r"(?i)(background(?:-color)?|selection-background-color|border(?!-radius)\b|border-(?:top|bottom|left|right))\s*:[^;{}]*;?"
        )
        for w in [root] + root.findChildren(QWidget):
            if isinstance(w, (QAbstractButton, QMenuBar, QGroupBox, QFrame)):
                continue
            if getattr(w, "objectName", lambda: "")() == "menu_separator_line":
                continue
            ss = w.styleSheet() or ""
            if not ss.strip():
                continue
            cleaned = color_re.sub("", ss)
            cleaned = re.sub(r";\s*;", ";", cleaned).strip()
            if cleaned != ss.strip():
                w.setStyleSheet(cleaned)

    def _ensure_menu_separator(self, menu_bar: QMenuBar, color: str) -> None:
        """Garante a linha inferior do menu sem mexer no layout."""
        if not menu_bar:
            return
        sep = getattr(self, "_menu_separator", None)
        if not isinstance(sep, QFrame) or sep.parent() is not menu_bar:
            sep = QFrame(menu_bar)
            sep.setObjectName("menu_separator_line")
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFrameShadow(QFrame.Shadow.Plain)
            sep.setLineWidth(1)
            sep.setFixedHeight(1)
            sep.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._menu_separator = sep
        sep.setStyleSheet(
            f"background-color: {color}; color: {color}; border: none;"
        )
        sep.setGeometry(0, max(0, menu_bar.height() - 1), menu_bar.width(), 1)
        sep.show()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            try:
                if isinstance(obj, (QMenu, QAbstractItemView)):
                    obj.setCursor(Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass
            try:
                if isinstance(obj, QMenuBar):
                    obj.setCursor(Qt.CursorShape.PointingHandCursor)
            except Exception:
                pass
            try:
                if isinstance(obj, QWidget):
                    obj.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    self._clear_local_color_qss(obj)
            except Exception:
                pass
        if event.type() == QEvent.Type.Resize and isinstance(obj, QMenuBar):
            try:
                color = getattr(self, "_menu_separator_color", None)
                if color:
                    self._ensure_menu_separator(obj, color)
            except Exception:
                pass
        return super().eventFilter(obj, event)

    def setup_menu(self):
        """Cria o Menu Superior (Arquivo + Ajuda)."""
        menu_bar = self.menuBar()
        menu_bar.setVisible(True)
        menu_bar.setNativeMenuBar(False)
        menu_bar.clear()

        # Estilo Profissional (Cinza, sem verde no topo)
        theme = self._get_theme_colors()
        menu_bg = theme["window"]
        menu_panel_bg = (
            "#3A3A3A" if self.current_theme == "Cinza (Gray)" else theme["button"]
        )
        menu_text = theme["text"]
        menu_hover = theme["button"]
        menu_border = self._get_theme_border_color()
        self._menu_separator_color = menu_border
        menu_bar.setStyleSheet(
            """
            QMenuBar {{
                background-color: {menu_bg};
                color: {menu_text};
                font-size: 10pt;
                border-bottom: 1px solid {menu_border};
                min-height: 24px;
                padding: 4px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 4px 10px;
                margin-top: 1px;
                cursor: pointing-hand;
            }}
            QMenuBar::item:selected {{
                background-color: {menu_hover};
                color: {menu_text};
                border-radius: 4px;
            }}
            QMenu {{
                background-color: {menu_panel_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 5px 20px 5px 20px;
                cursor: pointing-hand;
            }}
            QMenu::item:selected {{
                background-color: {menu_hover};
                color: {menu_text};
                border-radius: 2px;
            }}
        """.format(
                menu_bg=menu_bg,
                menu_panel_bg=menu_panel_bg,
                menu_text=menu_text,
                menu_hover=menu_hover,
                menu_border=menu_border,
            )
        )
        menu_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ensure_menu_separator(menu_bar, menu_border)

        # --- MENU ARQUIVO ---
        file_menu = menu_bar.addMenu(self.tr("menu_file"))
        file_menu.setCursor(Qt.CursorShape.PointingHandCursor)

        # Ação Reiniciar
        action_restart = file_menu.addAction(self.tr("menu_restart"))
        action_restart.setShortcut("Ctrl+R")
        action_restart.triggered.connect(self.restart_application)

        file_menu.addSeparator()

        # Ação Sair
        action_exit = file_menu.addAction(self.tr("menu_exit"))
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)

        # --- MENU AJUDA (ETAPAS) ---
        help_menu = menu_bar.addMenu(self.tr("menu_help"))
        help_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        action_help_quick = help_menu.addAction(self.tr("menu_help_quick"))
        action_help_quick.triggered.connect(self.show_quick_help)
        action_help_tour = help_menu.addAction(self.tr("menu_help_tour"))
        action_help_tour.triggered.connect(self.start_guided_tour)
        action_help_visual = help_menu.addAction(self.tr("menu_help_visual"))
        action_help_visual.triggered.connect(self.show_visual_guide)
        help_menu.addSeparator()
        action_help_step1 = help_menu.addAction(self.tr("manual_step_1"))
        action_help_step1.setShortcut("F1")
        action_help_step1.triggered.connect(
            lambda _=False: self.show_manual_step(1)
        )
        action_help_step2 = help_menu.addAction(self.tr("manual_step_2"))
        action_help_step2.setShortcut("F2")
        action_help_step2.triggered.connect(
            lambda _=False: self.show_manual_step(2)
        )
        action_help_step3 = help_menu.addAction(self.tr("manual_step_3"))
        action_help_step3.setShortcut("F3")
        action_help_step3.triggered.connect(
            lambda _=False: self.show_manual_step(3)
        )
        action_help_step4 = help_menu.addAction(self.tr("manual_step_4"))
        action_help_step4.setShortcut("F4")
        action_help_step4.triggered.connect(
            lambda _=False: self.show_manual_step(4)
        )

        self._apply_menu_action_cursors(menu_bar)

        # Menu Configurações removido - opções eram inúteis

    def show_optimizer_settings_dialog(self):
        """Abre o diálogo de configurações avançadas do otimizador."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("optimizer_advanced_title"))
        dialog.setMinimumSize(550, 400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # ========== AVISO NO TOPO ==========
        warning_label = QLabel(
            self.tr("optimizer_warning")
        )
        warning_label.setStyleSheet(
            """
            QLabel {
                background-color: #3a3a3a;
                color: #e0e0e0;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 10pt;
            }
        """
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # ========== SEÇÃO: FILTROS ==========
        filters_group = QGroupBox(self.tr("optimizer_filters_group"))
        filters_layout = QVBoxLayout()

        # Checkbox: Preservar comandos
        self.preserve_commands_cb = QCheckBox(
            self.tr("optimizer_preserve_commands")
        )
        self.preserve_commands_cb.setChecked(self.optimizer_config["preserve_commands"])
        self.preserve_commands_cb.setStyleSheet("QCheckBox { font-size: 9pt; }")
        filters_layout.addWidget(self.preserve_commands_cb)

        # Checkbox: Remover overlaps
        self.remove_overlaps_cb = QCheckBox(
            self.tr("optimizer_remove_overlaps")
        )
        self.remove_overlaps_cb.setChecked(self.optimizer_config["remove_overlaps"])
        self.remove_overlaps_cb.setStyleSheet("QCheckBox { font-size: 9pt; }")
        filters_layout.addWidget(self.remove_overlaps_cb)

        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # ========== SEÇÃO: SUBSTITUIÇÃO DE SÍMBOLOS ==========
        replace_group = QGroupBox(self.tr("optimizer_replace_group"))
        replace_layout = QHBoxLayout()

        # Label: "Trocar símbolo:"
        replace_label1 = QLabel(self.tr("optimizer_replace_symbol_label"))
        replace_layout.addWidget(replace_label1)

        # Input: Caractere original
        self.replace_symbol_input = QLineEdit(self.optimizer_config["replace_symbol"])
        self.replace_symbol_input.setMaxLength(1)
        self.replace_symbol_input.setFixedWidth(50)
        self.replace_symbol_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_symbol_input.setStyleSheet(
            "QLineEdit { font-size: 12pt; font-weight: bold; }"
        )
        replace_layout.addWidget(self.replace_symbol_input)

        # Label: "por:"
        replace_label2 = QLabel(self.tr("optimizer_replace_with_label"))
        replace_layout.addWidget(replace_label2)

        # Input: Novo caractere
        self.replace_with_input = QLineEdit(self.optimizer_config["replace_with"])
        self.replace_with_input.setMaxLength(1)
        self.replace_with_input.setFixedWidth(50)
        self.replace_with_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_with_input.setStyleSheet(
            "QLineEdit { font-size: 12pt; font-weight: bold; }"
        )
        replace_layout.addWidget(self.replace_with_input)

        replace_layout.addStretch()

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)

        # ========== INFORMAÇÃO ADICIONAL ==========
        info_label = QLabel(
            "💡 Dica: A substituição de símbolos é útil para converter caracteres especiais\nusados como espaços em ROMs antigas (@, _, etc.) por espaços reais."
        )
        info_label.setStyleSheet(
            """
            QLabel {
                color: #888888;
                font-size: 8pt;
                padding: 5px;
            }
        """
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # ========== BOTÕES ==========
        buttons_layout = QHBoxLayout()
        neutral_button_style = self._get_neutral_button_style()

        save_btn = QPushButton(self.tr("btn_save_ok"))
        save_btn.setStyleSheet(neutral_button_style)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(lambda: self.save_optimizer_config(dialog))

        cancel_btn = QPushButton(self.tr("btn_cancel_error"))
        self._apply_button_class(cancel_btn, "danger")
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
        self.optimizer_config["preserve_commands"] = (
            self.preserve_commands_cb.isChecked()
        )
        self.optimizer_config["remove_overlaps"] = self.remove_overlaps_cb.isChecked()
        self.optimizer_config["replace_symbol"] = (
            self.replace_symbol_input.text() or "@"
        )
        self.optimizer_config["replace_with"] = self.replace_with_input.text() or " "

        # Log das mudanças
        self.log("⚙️ Configurações do Otimizador atualizadas:")
        self.log(
            f"   • Preservar comandos: {self.optimizer_config['preserve_commands']}"
        )
        self.log(f"   • Remover overlaps: {self.optimizer_config['remove_overlaps']}")
        self.log(
            f"   • Substituir '{self.optimizer_config['replace_symbol']}' por '{self.optimizer_config['replace_with']}'"
        )

        QMessageBox.information(
            self,
            self.tr("optimizer_saved_title"),
            self.tr("optimizer_saved_message"),
        )

        dialog.accept()

    def _on_max_extraction_changed(self, state):
        """Atualiza modo de cobertura total e salva config."""
        if self.max_extraction_locked:
            self.max_extraction_mode = True
            if hasattr(self, "max_extract_cb"):
                self.max_extract_cb.blockSignals(True)
                self.max_extract_cb.setChecked(True)
                self.max_extract_cb.setEnabled(False)
                self.max_extract_cb.blockSignals(False)
            return
        self.max_extraction_mode = state == Qt.CheckState.Checked
        self.save_config()

    def _on_beginner_mode_changed(self, state):
        """Alterna o modo iniciante e aplica dicas visuais."""
        self.beginner_mode = state == Qt.CheckState.Checked
        self._apply_beginner_mode()
        self.save_config()

    def _set_highlight(self, widget, enabled: bool):
        """Sem brilho: remove qualquer efeito visual."""
        if not widget:
            return
        widget.setGraphicsEffect(None)

    def _apply_beginner_mode(self):
        """Ajusta interface para ficar mais simples no modo iniciante."""
        enabled = bool(getattr(self, "beginner_mode", False))

        # Mostrar/ocultar dicas
        if hasattr(self, "beginner_hint_extraction"):
            self.beginner_hint_extraction.setVisible(True)
        if hasattr(self, "beginner_hint_translation"):
            self.beginner_hint_translation.setVisible(True)
        if hasattr(self, "beginner_hint_reinsert"):
            self.beginner_hint_reinsert.setVisible(True)
        # Mantém opções avançadas visíveis; apenas mostra as dicas
        self._set_highlight(getattr(self, "select_rom_btn", None), False)
        self._set_highlight(getattr(self, "extract_btn", None), False)
        self._set_highlight(getattr(self, "optimize_btn", None), False)
        self._set_highlight(getattr(self, "sel_file_btn", None), False)
        self._set_highlight(getattr(self, "translate_btn", None), False)
        self._set_highlight(getattr(self, "select_reinsert_rom_btn", None), False)
        self._set_highlight(getattr(self, "select_translated_btn", None), False)
        self._set_highlight(getattr(self, "reinsert_btn", None), False)

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
        for (
            internal_key,
            translation_key,
        ) in ProjectConfig.THEME_TRANSLATION_KEYS.items():
            if self.tr(translation_key) == translated_name:
                return internal_key
        return translated_name  # Fallback if not found

    def get_all_translated_theme_names(self) -> list:
        """Get all theme names in translated form, maintaining order."""
        translated_names = []
        for internal_key in ProjectConfig.THEMES.keys():
            translated_names.append(self.get_translated_theme_name(internal_key))
        return translated_names

    def _read_startup_config(self) -> Dict:
        """Lê configuração persistida para decidir idioma inicial."""
        if not ProjectConfig.CONFIG_FILE.exists():
            return {}
        try:
            with open(ProjectConfig.CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _resolve_initial_ui_language(self, config: Dict) -> str:
        """Resolve idioma inicial: config > locale do sistema > EN."""
        ui_lang = config.get("ui_lang")
        if ui_lang and (ProjectConfig.I18N_DIR / f"{ui_lang}.json").exists():
            return ui_lang

        # Primeira execução (sem config): sempre EN-US
        return "en"

    def _format_lang_for_log(self) -> str:
        lang_map = {"en": "EN-US", "pt": "PT-BR"}
        return lang_map.get(self.current_ui_lang, self.current_ui_lang.upper())

    def _get_ui_lang_label(self, code: str) -> str:
        for label, lang_code in ProjectConfig.UI_LANGUAGES.items():
            if lang_code == code:
                return label
        # Fallback para inglês
        return "🇺🇸 English (US)"

    def _rom_identity_text(self, crc32: str | None = None, rom_size: int | None = None) -> str:
        crc32 = crc32 or self.current_rom_crc32
        rom_size = rom_size or self.current_rom_size
        if crc32 and rom_size is not None:
            return f"CRC32={crc32} | ROM_SIZE={rom_size}"
        if crc32:
            return f"CRC32={crc32}"
        return "CRC32=N/A | ROM_SIZE=N/A"

    def _load_forensic_crc_db(self) -> dict:
        """Carrega base local CRC32/ROM_SIZE para engine/ano (sem nomes de jogos)."""
        if hasattr(self, "_forensic_crc_db"):
            return self._forensic_crc_db
        db = {}
        try:
            if ProjectConfig.FORENSIC_CRC_DB_FILE.exists():
                with open(ProjectConfig.FORENSIC_CRC_DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    db = data
                elif isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        crc = str(item.get("crc32", "")).upper()
                        size = item.get("rom_size")
                        if crc and size is not None:
                            db[f"{crc}|{size}"] = {
                                "engine": item.get("engine"),
                                "year": item.get("year"),
                            }
                        elif crc:
                            db[crc] = {
                                "engine": item.get("engine"),
                                "year": item.get("year"),
                            }
        except Exception:
            db = {}
        self._forensic_crc_db = db
        return db

    def _get_crc_forensic_entry(self) -> dict | None:
        """Busca engine/ano por CRC32/ROM_SIZE."""
        crc = (self.current_rom_crc32 or "").upper()
        rom_size = self.current_rom_size
        if not crc:
            return None
        db = self._load_forensic_crc_db()
        key = f"{crc}|{rom_size}" if rom_size is not None else crc
        return db.get(key) or db.get(crc)

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
            translated_names.append(
                self.get_translated_source_language_name(internal_key)
            )
        return translated_names

    def check_eula_and_license(self):
        """COMMERCIAL: Check EULA acceptance and license activation."""
        if SecurityManager is None:
            return

        # Check EULA
        if not SecurityManager.is_eula_accepted():
            eula_dialog = QDialog(self)
            eula_dialog.setWindowTitle(self.tr("eula_title"))
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
            accept_btn = QPushButton(self.tr("btn_accept"))
            accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reject_btn = QPushButton(self.tr("btn_reject"))
            reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def on_accept():
                SecurityManager.accept_eula()
                eula_dialog.accept()

            def on_reject():
                QMessageBox.critical(
                    eula_dialog,
                    self.tr("eula_required_title"),
                    self.tr("eula_required_message"),
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
            license_dialog.setWindowTitle(self.tr("license_title"))
            license_dialog.setMinimumSize(500, 300)
            license_dialog.setModal(True)

            layout = QVBoxLayout(license_dialog)

            info_label = QLabel(self.tr("license_info"))
            info_label.setWordWrap(True)
            info_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(info_label)

            key_label = QLabel(self.tr("license_key_label"))
            layout.addWidget(key_label)

            key_input = QLineEdit()
            key_input.setPlaceholderText(self.tr("license_key_placeholder"))
            layout.addWidget(key_input)

            status_label = QLabel("")
            status_label.setStyleSheet("color: red;")
            layout.addWidget(status_label)

            button_layout = QHBoxLayout()
            activate_btn = QPushButton(self.tr("btn_activate"))
            activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            skip_btn = QPushButton(self.tr("exit"))
            skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def on_activate():
                key = key_input.text().strip()
                valid, msg = SecurityManager.validate_license(key)
                if valid:
                    status_label.setStyleSheet("color: green;")
                    status_label.setText("[OK] " + msg)
                    QMessageBox.information(
                        license_dialog,
                        self.tr("license_success_title"),
                        self.tr("license_success_message"),
                    )
                    license_dialog.accept()
                else:
                    status_label.setStyleSheet("color: red;")
                    status_label.setText("[ERROR] " + msg)

            def on_skip():
                QMessageBox.warning(
                    license_dialog,
                    self.tr("license_required_title"),
                    self.tr("license_required_message"),
                )
                sys.exit(0)

            activate_btn.clicked.connect(on_activate)
            skip_btn.clicked.connect(on_skip)

            button_layout.addWidget(skip_btn)
            button_layout.addWidget(activate_btn)
            layout.addLayout(button_layout)

            license_dialog.exec()

    def update_window_title(self):
        self.setWindowTitle(self.tr("window_title"))

    def _apply_initial_window_size(self):
        """Define tamanho inicial profissional baseado na tela."""
        screen = self.screen()
        if screen is None:
            # Fallback seguro
            self.setMinimumSize(1000, 700)
            self.resize(1200, 800)
            return

        available = screen.availableGeometry()
        avail_w = available.width()
        avail_h = available.height()

        # Mínimos adaptativos para telas menores
        min_w = 1000 if avail_w >= 1100 else max(800, int(avail_w * 0.8))
        min_h = 700 if avail_h >= 800 else max(600, int(avail_h * 0.8))

        width = int(avail_w * 0.8)
        height = int(avail_h * 0.8)

        width = max(width, min_w)
        height = max(height, min_h)

        self.setMinimumSize(min_w, min_h)
        self.resize(width, height)
        self._center_on_screen()

    def _center_on_screen(self):
        """Centraliza a janela na tela disponível."""
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _ensure_window_visible(self):
        """Garante que a janela esteja visível na tela atual."""
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        if not available.intersects(frame):
            self._center_on_screen()

    def _update_action_states(self):
        """Habilita/desabilita ações principais com tooltips claros."""
        # ROM selecionada
        has_rom = bool(
            self.original_rom_path and os.path.exists(self.original_rom_path)
        )
        platform_ready = True
        if hasattr(self, "platform_combo"):
            selected_text = self.platform_combo.currentText()
            data = ProjectConfig.PLATFORMS.get(selected_text)
            if not data or data.get("code") == "separator":
                platform_ready = False
            else:
                platform_ready = bool(data.get("ready", False))
        rom_tooltip = (
            self.tr("platform_tooltip")
            if not platform_ready
            else self.tr("tooltip_select_rom")
        )
        extract_tip = self.tr("tooltip_extract_texts")
        forensic_tip = self.tr("tooltip_forensic_analysis")
        ascii_tip = self.tr("tooltip_ascii_probe")
        optimize_tip = self.tr("tooltip_optimize_data")
        translate_tip = self.tr("tooltip_translate_ai")
        reinsert_tip = self.tr("tooltip_reinsert")

        # Extração/Análises: exigem ROM válida e plataforma pronta
        if hasattr(self, "extract_btn"):
            is_extracting = bool(
                getattr(self, "extract_thread", None)
                and self.extract_thread.isRunning()
            )
            can_extract = platform_ready and has_rom and not is_extracting
            self.extract_btn.setEnabled(can_extract)
            self.extract_btn.setToolTip(
                extract_tip if can_extract else rom_tooltip
            )
        if hasattr(self, "forensic_analysis_btn"):
            can_analyze = platform_ready and has_rom
            self.forensic_analysis_btn.setEnabled(can_analyze)
            self.forensic_analysis_btn.setToolTip(
                forensic_tip if can_analyze else rom_tooltip
            )
        if hasattr(self, "ascii_probe_btn"):
            can_probe = platform_ready and has_rom
            self.ascii_probe_btn.setEnabled(can_probe)
            self.ascii_probe_btn.setToolTip(
                ascii_tip if can_probe else rom_tooltip
            )

        # Otimização: exige arquivo extraído
        has_extracted = bool(
            self.extracted_file and os.path.exists(self.extracted_file)
        )
        if hasattr(self, "optimize_btn"):
            is_optimizing = bool(
                getattr(self, "optimize_thread", None)
                and self.optimize_thread.isRunning()
            )
            can_optimize = has_extracted and not is_optimizing
            self.optimize_btn.setEnabled(can_optimize)
            self.optimize_btn.setToolTip(
                optimize_tip
                if can_optimize
                else self.tr("tooltip_select_extracted_file")
            )

        # Tradução: exige arquivo otimizado
        has_optimized = bool(
            self.optimized_file and os.path.exists(self.optimized_file)
        )
        has_tilemap_jsonl = bool(
            self._resolve_tilemap_jsonl_for_translation(self.optimized_file)
        )
        if hasattr(self, "translate_btn"):
            can_translate = has_optimized or has_tilemap_jsonl
            self.translate_btn.setEnabled(can_translate)
            self.translate_btn.setToolTip(
                translate_tip
                if can_translate
                else self.tr("tooltip_select_optimized_file")
            )

        # Reinserção: exige ROM original + arquivo traduzido
        has_translated = bool(
            self.translated_file and os.path.exists(self.translated_file)
        )
        if hasattr(self, "reinsert_btn"):
            can_reinsert = has_rom and has_translated
            self.reinsert_btn.setEnabled(can_reinsert)
            self.reinsert_btn.setToolTip(
                reinsert_tip
                if can_reinsert
                else self.tr("tooltip_select_reinsert_files")
            )

    def _get_progress_bar_style(self) -> str:
        """Estilo de barra de progresso em cinza/preto."""
        return """
        QProgressBar {
            border-radius: 7px;
            padding: 2px;
        }
        QProgressBar::chunk {
            border-radius: 7px;
        }
        """

    def _get_unified_button_style(self) -> str:
        """Estilo único (pílula) para todos os botões."""
        theme = self._get_theme_colors()
        accent = theme.get("accent", "#D4AF37")
        text = theme.get("text", "#ffffff")
        button = theme.get("button", "#202022")
        window = theme.get("window", "#161618")
        base_color = QColor(button)
        window_color = QColor(window)
        text_disabled = "#9A9A9A"
        disabled_bg = window_color.darker(110).name()
        disabled_border = self._get_theme_border_color()
        normal_top = base_color.lighter(115).name()
        normal_mid1 = base_color.darker(105).name()
        normal_mid2 = base_color.darker(115).name()
        normal_bottom = window_color.darker(115).name()
        hover_top = base_color.lighter(125).name()
        hover_mid1 = base_color.lighter(110).name()
        hover_mid2 = base_color.darker(105).name()
        hover_bottom = base_color.darker(120).name()
        press_top = base_color.darker(110).name()
        press_bottom = base_color.darker(125).name()
        disabled_top = base_color.lighter(105).name()
        disabled_mid1 = base_color.darker(110).name()
        disabled_mid2 = base_color.darker(120).name()
        disabled_bottom = window_color.darker(120).name()
        border = base_color.darker(140).name()
        return f"""
        QPushButton {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {normal_top},
                stop: 0.45 {normal_mid1},
                stop: 0.55 {normal_mid2},
                stop: 1 {normal_bottom}
            );
            color: {text};
            font-size: 10.5pt;
            font-weight: 500;
            border-radius: 16px;
            border: 1px solid {border};
            padding: 6px 18px;
        }}
        QPushButton:hover {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {hover_top},
                stop: 0.45 {hover_mid1},
                stop: 0.55 {hover_mid2},
                stop: 1 {hover_bottom}
            );
        }}
        QPushButton:pressed {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {press_top},
                stop: 1 {press_bottom}
            );
        }}
        QPushButton:disabled {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {disabled_top},
                stop: 0.45 {disabled_mid1},
                stop: 0.55 {disabled_mid2},
                stop: 1 {disabled_bottom}
            );
            color: {text_disabled};
            border: 1px solid {disabled_border};
            border-radius: 16px;
        }}
        QPushButton[class="primary"] {{
            background: {accent};
            border: 1px solid {accent};
            color: #FFFFFF;
            font-weight: 600;
        }}
        QPushButton[class="primary"]:hover {{
            background: {accent};
            border: 1px solid {accent};
        }}
        QPushButton[class="primary"]:pressed {{
            background: {accent};
            border: 1px solid {accent};
        }}
        QPushButton[class="primaryOutline"] {{
            background: {button};
            border: 2px solid {accent};
            color: {text};
            font-weight: 600;
        }}
        QPushButton[class="primaryOutline"]:hover {{
            background: {window};
        }}
        QPushButton[class="primaryOutline"]:pressed {{
            background: {window};
        }}
        QPushButton[class="danger"] {{
            background: #EF4444;
            border: 1px solid #C83737;
            color: #FFFFFF;
            font-weight: 600;
        }}
        QPushButton[class="danger"]:hover {{
            background: #E13A3A;
            border: 1px solid #E13A3A;
        }}
        QPushButton[class="danger"]:pressed {{
            background: #C83737;
            border: 1px solid #C83737;
        }}
        QPushButton[class="dangerOutline"] {{
            background: {button};
            border: 2px solid #EF4444;
            color: #FFECEC;
            font-weight: 600;
        }}
        QPushButton[class="dangerOutline"]:hover {{
            background: {window};
        }}
        QPushButton[class="primary"]:disabled,
        QPushButton[class="danger"]:disabled,
        QPushButton[class="primaryOutline"]:disabled,
        QPushButton[class="dangerOutline"]:disabled {{
            background: {disabled_bg};
            border: 1px solid {disabled_border};
            color: {text_disabled};
        }}
        """

    def _get_primary_button_style(self) -> str:
        """Estilo principal com accent único."""
        theme = self._get_theme_colors()
        accent = theme.get("accent", "#D4AF37")
        accent_color = QColor(accent)
        accent_hover = accent_color.lighter(115).name()
        accent_pressed = accent_color.darker(115).name()
        disabled_bg = QColor(theme["window"]).darker(110).name()
        disabled_border = self._get_theme_border_color()
        text_disabled = "#9A9A9A"
        return f"""
        QPushButton {{
            background-color: {accent};
            color: #ffffff;
            font-size: 10.5pt;
            font-weight: 600;
            border-radius: 16px;
            border: 1px solid {accent};
            padding: 6px 18px;
        }}
        QPushButton:hover {{
            background-color: {accent_hover};
            border: 1px solid {accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {accent_pressed};
            border: 1px solid {accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {disabled_bg};
            color: {text_disabled};
            border: 1px solid {disabled_border};
        }}
        """

    def _get_neutral_button_style(self) -> str:
        """Estilo neutro (unificado)."""
        return self._get_unified_button_style()

    def _ensure_rom_output_dir(self, rom_dir: str, crc32_full: str) -> str:
        """Cria (se necessário) uma pasta de saída por CRC32."""
        if not rom_dir or not crc32_full:
            return rom_dir
        output_dir = os.path.join(rom_dir, crc32_full)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _set_text_dir_from_output_dir(self, output_dir: str):
        """Define pasta padrão para seleção de TXT baseada na saída atual."""
        if not output_dir or not os.path.isdir(output_dir):
            return
        aux_dir = os.path.join(output_dir, "_interno")
        has_jsonl = False
        has_all_text = False
        try:
            has_jsonl = any(
                fn.endswith("_pure_text.jsonl") for fn in os.listdir(output_dir)
            )
            if os.path.isdir(aux_dir):
                has_all_text = any(
                    fn.endswith("_all_text.jsonl") for fn in os.listdir(aux_dir)
                )
        except OSError:
            has_jsonl = False
        if self.max_extraction_mode and has_all_text:
            self.last_text_dir = aux_dir
        elif has_jsonl:
            self.last_text_dir = output_dir
        elif os.path.isdir(aux_dir):
            self.last_text_dir = aux_dir
        else:
            self.last_text_dir = output_dir

    def _get_output_dir_for_current_rom(self) -> str | None:
        """Retorna pasta CRC32 da ROM atual, se existir."""
        if self.current_output_dir and os.path.isdir(self.current_output_dir):
            return self.current_output_dir
        if self.original_rom_path and self.current_rom_crc32:
            candidate = os.path.join(
                os.path.dirname(self.original_rom_path), self.current_rom_crc32
            )
            if os.path.isdir(candidate):
                return candidate
        return None

    def _resolve_tilemap_jsonl_for_translation(self, input_file: str | None) -> str | None:
        """Resolve JSONL tilemap (pure_text) para tradução direta, se existir."""
        candidates = []
        seen = set()

        def _add_candidate(p: str | None):
            if not p:
                return
            if p in seen:
                return
            seen.add(p)
            candidates.append(p)

        # 1) Se o arquivo selecionado já for JSONL, valida direto
        if input_file and input_file.lower().endswith(".jsonl"):
            if _jsonl_has_tilemap_entries(input_file):
                return input_file

        # 2) Tenta deduzir pela pasta do arquivo atual
        if input_file:
            p = Path(input_file)
            output_dir = p.parent.parent if p.parent.name == "_interno" else p.parent
            crc = self._infer_crc32_from_filename(input_file) or self.current_rom_crc32
            if crc and output_dir:
                _add_candidate(os.path.join(output_dir, f"{crc}_pure_text.jsonl"))

        # 3) Tenta pasta CRC32 atual
        output_dir = self._get_output_dir_for_current_rom()
        if output_dir and self.current_rom_crc32:
            _add_candidate(os.path.join(output_dir, f"{self.current_rom_crc32}_pure_text.jsonl"))

        # 4) Valida candidatos diretos
        for cand in candidates:
            if os.path.exists(cand) and _jsonl_has_tilemap_entries(cand):
                return cand

        # 5) Fallback: varre _pure_text.jsonl na pasta de saída
        if output_dir and os.path.isdir(output_dir):
            try:
                for fn in os.listdir(output_dir):
                    if not fn.endswith("_pure_text.jsonl"):
                        continue
                    cand = os.path.join(output_dir, fn)
                    if _jsonl_has_tilemap_entries(cand):
                        return cand
            except Exception:
                return None

        return None

    def _infer_crc32_from_filename(self, file_path: str) -> str | None:
        """Extrai CRC32 do nome do arquivo, se existir."""
        try:
            name = Path(file_path).name
            m = re.match(r"([0-9A-Fa-f]{8})_", name)
            return m.group(1).upper() if m else None
        except Exception:
            return None

    def _set_output_dir_from_file(self, file_path: str):
        """Define pasta de saída/CRC32 a partir do arquivo selecionado."""
        if not file_path:
            return
        p = Path(file_path)
        if p.parent.name == "_interno":
            output_dir = p.parent.parent
        else:
            output_dir = p.parent
        if output_dir and output_dir.is_dir():
            self.current_output_dir = str(output_dir)
            self._set_text_dir_from_output_dir(self.current_output_dir)
            crc = self._infer_crc32_from_filename(file_path)
            if crc and not self.current_rom_crc32:
                self.current_rom_crc32 = crc
            self.log(
                self.tr("hint_files_location").format(folder=str(output_dir))
            )

    def _update_internal_path(self, old_path: str, new_path: str):
        """Atualiza referências internas quando um arquivo é movido."""
        for attr in (
            "extracted_file",
            "optimized_file",
            "translated_file",
            "last_clean_blocks",
        ):
            if getattr(self, attr, None) == old_path:
                setattr(self, attr, new_path)

    def _stash_auxiliary_outputs(self, output_dir: str, crc32_full: str):
        """Move arquivos auxiliares para subpasta _interno.

        Arquivos protegidos que PERMANECEM no root:
          - {CRC32}_pure_text.jsonl
          - {CRC32}_reinsertion_mapping.json
          - {CRC32}_report.txt
          - {CRC32}_proof.json
          - {CRC32}_translated*.jsonl
          - {CRC32}_patched.*
        Todo o resto {CRC32}_* vai para _interno/.
        """
        if not output_dir or not crc32_full:
            return
        prefix = f"{crc32_full}_"
        keep = {
            f"{crc32_full}_pure_text.jsonl",
            f"{crc32_full}_reinsertion_mapping.json",
            f"{crc32_full}_report.txt",
            f"{crc32_full}_proof.json",
        }
        aux_dir = os.path.join(output_dir, "_interno")
        os.makedirs(aux_dir, exist_ok=True)
        try:
            for fn in os.listdir(output_dir):
                if not fn.startswith(prefix):
                    continue
                if fn in keep:
                    continue
                # Protege translated*.jsonl (translated.jsonl, translated_fixed.jsonl, etc.)
                fn_lower = fn.lower()
                if "translated" in fn_lower and fn_lower.endswith(".jsonl"):
                    continue
                # Protege patched.* (ROM patcheada)
                if fn_lower.startswith(f"{crc32_full.lower()}_patched"):
                    continue
                src = os.path.join(output_dir, fn)
                if os.path.isdir(src):
                    continue
                dst = os.path.join(aux_dir, fn)
                if os.path.abspath(src) == os.path.abspath(dst):
                    continue
                shutil.move(src, dst)
                self._update_internal_path(src, dst)
        except Exception as e:
            self.log(f"[WARN] Falha ao mover auxiliares: {_sanitize_error(e)}")
        self._set_text_dir_from_output_dir(output_dir)

    def _open_output_select_main(self, output_dir: str, crc32_full: str):
        """Abre o Explorer selecionando o pure_text.jsonl (extração)."""
        primary = os.path.join(output_dir, f"{crc32_full}_pure_text.jsonl")
        self._explorer_select(primary, output_dir)

    @staticmethod
    def _explorer_select(file_path: str, fallback_dir: str = ""):
        """Abre Explorer com /select no arquivo. Fallback para pasta."""
        try:
            if os.path.isfile(file_path):
                subprocess.Popen(f'explorer /select,"{file_path}"')
            elif fallback_dir and os.path.isdir(fallback_dir):
                subprocess.Popen(f'explorer /select,"{fallback_dir}"')
        except Exception:
            pass

    def _set_extracted_from_output_dir(self, output_dir: str, crc32_full: str):
        """Define o arquivo base para otimização dentro da pasta CRC32/_interno."""
        if not output_dir or not crc32_full:
            return
        aux_dir = os.path.join(output_dir, "_interno")
        candidates = [
            os.path.join(aux_dir, f"{crc32_full}_clean_blocks.txt"),
            os.path.join(aux_dir, f"{crc32_full}_extracted_texts.txt"),
            os.path.join(aux_dir, f"{crc32_full}_extracted.txt"),
            os.path.join(aux_dir, f"{crc32_full}_all_text.jsonl"),
            os.path.join(output_dir, f"{crc32_full}_pure_text.jsonl"),
        ]
        for p in candidates:
            if os.path.exists(p):
                # Preferência: clean_blocks/extracted no _interno, senão JSONL base
                self.extracted_file = p
                if p.endswith("_clean_blocks.txt"):
                    self.last_clean_blocks = p
                return

    def _organize_crc32_outputs(self, base_dir: str, crc32_full: str) -> str | None:
        """Move arquivos gerados para pasta por CRC32 para evitar bagunça."""
        if not base_dir or not crc32_full:
            return None
        output_dir = self.current_output_dir or self._ensure_rom_output_dir(
            base_dir, crc32_full
        )
        try:
            if os.path.isdir(base_dir) and os.path.isdir(output_dir):
                # Se base_dir estiver dentro de output_dir, não remove de lá
                try:
                    if os.path.commonpath([base_dir, output_dir]) != output_dir:
                        for fn in os.listdir(base_dir):
                            if not fn.startswith(f"{crc32_full}_"):
                                continue
                            src = os.path.join(base_dir, fn)
                            if os.path.isdir(src):
                                continue
                            dst = os.path.join(output_dir, fn)
                            if os.path.abspath(src) == os.path.abspath(dst):
                                continue
                            shutil.move(src, dst)
                            self._update_internal_path(src, dst)
                except ValueError:
                    pass
        except Exception as e:
            self.log(f"[WARN] Falha ao organizar saídas: {_sanitize_error(e)}")
        self.current_output_dir = output_dir
        self._stash_auxiliary_outputs(output_dir, crc32_full)
        self._set_extracted_from_output_dir(output_dir, crc32_full)
        return output_dir

    def _scan_ascii_sequences(self, rom_path: str, min_len: int = 2, max_len: int = 160) -> list:
        """Varre ROM e retorna sequências ASCII imprimíveis (offset, texto)."""
        try:
            data = Path(rom_path).read_bytes()
        except Exception:
            return []

        results = []
        start = None
        for i, b in enumerate(data):
            if 32 <= b <= 126:  # ASCII imprimível
                if start is None:
                    start = i
            else:
                if start is not None:
                    length = i - start
                    if length >= min_len:
                        raw = data[start:i]
                        if len(raw) > max_len:
                            raw = raw[:max_len]
                        try:
                            text = raw.decode("ascii", errors="ignore")
                        except Exception:
                            text = ""
                        if text:
                            if any(ch.isalnum() for ch in text):
                                results.append((start, text))
                    start = None

        if start is not None:
            raw = data[start:]
            if len(raw) >= min_len:
                if len(raw) > max_len:
                    raw = raw[:max_len]
                try:
                    text = raw.decode("ascii", errors="ignore")
                except Exception:
                    text = ""
                if text and any(ch.isalnum() for ch in text):
                    results.append((start, text))

        return results

    def _build_max_coverage_jsonl(
        self, rom_path: str, output_dir: str, crc32_full: str
    ) -> tuple[str | None, int, int, int]:
        """Gera um JSONL completo (base + ASCII bruto) em _interno."""
        if not rom_path or not output_dir or not crc32_full:
            return None, 0, 0, 0

        base_jsonl = os.path.join(output_dir, f"{crc32_full}_pure_text.jsonl")
        if not os.path.exists(base_jsonl):
            return None, 0, 0, 0

        aux_dir = os.path.join(output_dir, "_interno")
        os.makedirs(aux_dir, exist_ok=True)
        full_jsonl = os.path.join(aux_dir, f"{crc32_full}_all_text.jsonl")

        entries = []
        existing = set()
        max_id = 0

        def _parse_offset(val):
            if val is None:
                return 0
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                s = val.strip()
                try:
                    return int(s, 16) if s.lower().startswith("0x") else int(s)
                except ValueError:
                    return 0
            return 0

        try:
            with open(base_jsonl, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = (
                        obj.get("text_src")
                        or obj.get("text")
                        or obj.get("original_text")
                        or obj.get("translated_text")
                        or ""
                    )
                    if not isinstance(text, str) or not text.strip():
                        continue
                    off = _parse_offset(obj.get("offset"))
                    existing.add((off, text))
                    if isinstance(obj.get("id"), int):
                        max_id = max(max_id, obj["id"])
                    entries.append(obj)
        except Exception:
            return None, 0, 0, 0

        # Scan ASCII bruto
        ascii_hits = self._scan_ascii_sequences(rom_path)
        added = 0
        next_id = max_id + 1
        for off, text in ascii_hits:
            if (off, text) in existing:
                continue
            obj = {
                "id": next_id,
                "offset": f"0x{off:06X}",
                "text_src": text,
                "max_len_bytes": len(text.encode("utf-8", errors="ignore")) + 1,
                "encoding": "ascii",
                "source": "ASCII_BRUTE",
                "reinsertion_safe": False,
                "confidence": "low",
                "note": "raw_ascii_scan",
            }
            next_id += 1
            entries.append(obj)
            added += 1

        # Scan tilemap (SMS/GG/SG) sem emulador
        tile_added = 0
        try:
            ext = Path(rom_path).suffix.lower()
            if ext in [".sms", ".gg", ".sg"]:
                from core.MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL import (
                    UniversalMasterSystemExtractor,
                )

                uni = UniversalMasterSystemExtractor(rom_path)
                tile_items = uni._extract_tilemap_probe()
                for it in tile_items:
                    text = (it.get("clean") or it.get("decoded") or "").strip()
                    if not text:
                        continue
                    off = int(it.get("offset", 0) or 0)
                    if (off, text) in existing:
                        continue
                    obj = {
                        "id": next_id,
                        "offset": f"0x{off:06X}",
                        "text_src": text,
                        "max_len_bytes": it.get("max_len")
                        or (len(text.encode("utf-8", errors="ignore")) + 1),
                        "encoding": it.get("encoding", "tile"),
                        "source": it.get("source", "TILEMAP_PROBE"),
                        "reinsertion_safe": False,
                        "confidence": float(it.get("confidence", 0.30)),
                        "note": "tilemap_probe",
                        "raw_bytes_hex": it.get("raw_bytes_hex", ""),
                    }
                    next_id += 1
                    entries.append(obj)
                    tile_added += 1
        except Exception:
            pass

        # Garante IDs para entradas sem id
        for obj in entries:
            if obj.get("id") is None:
                obj["id"] = next_id
                next_id += 1

        try:
            with open(full_jsonl, "w", encoding="utf-8", newline="\n") as f:
                for obj in entries:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            return None, 0, 0, 0

        # Atualiza report com total do modo cobertura total
        try:
            report_path = os.path.join(output_dir, f"{crc32_full}_report.txt")
            with open(report_path, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write("[INFO] COBERTURA TOTAL (ASCII BRUTE)\n")
                f.write(f"TOTAL_ENTRADAS={len(entries)}\n")
                f.write(f"ADICIONADAS_ASCII={added}\n")
                f.write(f"ADICIONADAS_TILEMAP={tile_added}\n")
        except Exception:
            pass

        return full_jsonl, len(entries), added, tile_added

    def _apply_max_extraction(self, rom_path: str, output_dir: str, crc32_full: str):
        """Se modo cobertura total estiver ativo, gera arquivo completo e usa como base."""
        if not self.max_extraction_mode:
            return
        if not rom_path or not output_dir or not crc32_full:
            return

        self.log(self.tr("max_extraction_scan_start"))
        full_jsonl, total, added, tile_added = self._build_max_coverage_jsonl(
            rom_path, output_dir, crc32_full
        )
        if not full_jsonl:
            self.log(self.tr("max_extraction_missing_base"))
            return

        # Cobertura Total gera arquivo em _interno para diagnóstico APENAS.
        # NÃO se torna o arquivo de tradução (self.extracted_file inalterado).
        self._set_text_dir_from_output_dir(output_dir)
        self.log(
            self.tr("max_extraction_done").format(
                total=total, added=added, tile=tile_added, file=full_jsonl
            )
        )
        if tile_added > 0:
            self._activate_graphics_tab("tilemap detectado")
        self._update_action_states()

    def _create_rom_backup(self, rom_path: str, output_dir: str) -> str | None:
        """Cria backup da ROM original antes da reinserção."""
        try:
            base = Path(rom_path).stem
            ext = Path(rom_path).suffix
            backup_path = os.path.join(output_dir, f"{base}_BACKUP{ext}")
            if os.path.exists(backup_path):
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(
                    output_dir, f"{base}_BACKUP_{stamp}{ext}"
                )
            shutil.copy2(rom_path, backup_path)
            return backup_path
        except Exception as e:
            self.log(f"[WARN] Falha ao criar backup: {_sanitize_error(e)}")
            return None

    def toggle_log_panel(self):
        """Mostra/oculta o painel de log."""
        is_visible = self.log_group.isVisible()
        self.log_group.setVisible(not is_visible)
        self.log_toggle_btn.setText(
            self.tr("log_show") if is_visible else self.tr("log_hide")
        )

    def init_ui(self):
        self.setWindowTitle(self.tr("window_title"))
        self._apply_initial_window_size()

        # --- NOVO: Configura o Menu Superior ---
        self.setup_menu()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self.create_extraction_tab(), self._clean_tab_label(self.tr("tab1"))
        )

        # Create Graphics Lab tab (index 1 - antes da Tradução)
        if GraphicLabTab:
            self.graphics_lab_tab = GraphicLabTab(self)
            self.tabs.addTab(
                self.graphics_lab_tab, self._clean_tab_label(self.tr("tab2"))
            )
        else:
            graphics_placeholder = QWidget()
            graphics_placeholder_layout = QVBoxLayout(graphics_placeholder)
            graphics_placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Título
            self.graphics_title_label = QLabel(self.tr("graphics_lab_title"))
            self.graphics_title_label.setStyleSheet(
                "font-size: 18px; font-weight: bold; color: #b0b0b0; margin-bottom: 10px;"
            )
            self.graphics_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            graphics_placeholder_layout.addWidget(self.graphics_title_label)

            # Mensagem de desenvolvimento
            self.graphics_msg_label = QLabel(self.tr("graphics_placeholder_msg"))
            self.graphics_msg_label.setStyleSheet(
                "font-size: 14px; color: #888888; padding: 20px;"
            )
            self.graphics_msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.graphics_msg_label.setWordWrap(True)
            graphics_placeholder_layout.addWidget(self.graphics_msg_label)

            # Observação técnica
            self.graphics_tech_note = QLabel(self.tr("graphics_tech_note"))
            self.graphics_tech_note.setStyleSheet(
                """
                font-size: 12px;
                color: #666666;
                background-color: #1a1a1a;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #333333;
            """
            )
            self.graphics_tech_note.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.graphics_tech_note.setWordWrap(True)
            graphics_placeholder_layout.addWidget(self.graphics_tech_note)

            graphics_placeholder_layout.addStretch()
            self.tabs.addTab(
                graphics_placeholder, self._clean_tab_label(self.tr("tab2"))
            )

        self.tabs.addTab(
            self.create_translation_tab(), self._clean_tab_label(self.tr("tab3"))
        )
        self.tabs.addTab(
            self.create_reinsertion_tab(), self._clean_tab_label(self.tr("tab4"))
        )
        self.tabs.addTab(
            self.create_settings_tab(), self._clean_tab_label(self.tr("tab5"))
        )
        left_layout.addWidget(self.tabs)
        if not self.developer_mode:
            try:
                self.tabs.setTabVisible(1, False)
            except Exception:
                self.tabs.setTabEnabled(1, False)
        main_layout.addWidget(left_panel, 3)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(8, 8, 8, 8)

        # Log de Operações (colapsável)
        log_header_layout = QHBoxLayout()
        self.log_title_label = QLabel(self.tr("log"))
        self.log_title_label.setStyleSheet("color: #b0b0b0; font-weight: bold;")
        self.log_toggle_btn = QPushButton(self.tr("log_hide"))
        self.log_toggle_btn.setObjectName("log_toggle_btn")
        self.log_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_toggle_btn.setFixedHeight(26)
        self.log_toggle_btn.setStyleSheet(self._get_unified_button_style())
        self.log_toggle_btn.clicked.connect(self.toggle_log_panel)
        log_header_layout.addWidget(self.log_title_label)
        log_header_layout.addStretch()
        log_header_layout.addWidget(self.log_toggle_btn)
        right_layout.addLayout(log_header_layout)

        self.log_group = QGroupBox()
        self.log_group.setObjectName("log_group")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(260)
        self.log_text.setStyleSheet("")
        # Fonte Monospace para o Log (Fica mais "Hacker/Dev")
        font_log = QFont("Consolas", 9)
        self.log_text.setFont(font_log)

        log_layout.addWidget(self.log_text)
        self.log_group.setLayout(log_layout)
        right_layout.addWidget(self.log_group)
        # Inicializa texto do botão de log
        self.log_toggle_btn.setText(self.tr("log_hide"))

        # ========== PAINEL DE TRADUÇÃO EM TEMPO REAL (LADO DIREITO) ==========
        self.realtime_group = QGroupBox(self.tr("realtime_group_title"))
        self.realtime_group.setObjectName("realtime_translation_group")
        theme = self._get_theme_colors()
        panel_border = self._get_theme_border_color()
        text_muted = QColor(theme["text"]).darker(140).name()
        self.realtime_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {panel_border};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {text_muted};
            }}
        """
        )
        realtime_layout = QVBoxLayout()

        self.realtime_original_label = QLabel(self.tr("realtime_original_label"))
        self.realtime_original_label.setStyleSheet(
            "color: #b0b0b0; font-size: 11pt; padding: 8px;"
        )
        self.realtime_original_label.setWordWrap(True)
        realtime_layout.addWidget(self.realtime_original_label)

        self.realtime_translated_label = QLabel(self.tr("realtime_translated_label"))
        self.realtime_translated_label.setStyleSheet(
            "color: #e0e0e0; font-size: 11pt; font-weight: bold; padding: 8px;"
        )
        self.realtime_translated_label.setWordWrap(True)
        realtime_layout.addWidget(self.realtime_translated_label)

        self.realtime_info_label = QLabel(self.tr("realtime_info_label"))
        self.realtime_info_label.setStyleSheet(
            "color: #9a9a9a; font-size: 10pt; padding: 5px;"
        )
        realtime_layout.addWidget(self.realtime_info_label)

        self.realtime_group.setLayout(realtime_layout)
        right_layout.addWidget(self.realtime_group)

        # --- ALTERAÇÃO: REMOVIDOS OS BOTÕES GIGANTES "REINICIAR" E "SAIR" DAQUI ---
        # Eles agora estão no Menu Superior "Arquivo".
        # Isso limpa o visual e deixa mais profissional.

        # Copyright Footer
        copyright_label = QLabel(self.tr("developer_footer"))
        copyright_label.setObjectName("copyright_label")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet(
            "color:#888;font-size:9pt;font-weight:bold; margin-top: 10px;"
        )
        pro_badge = QLabel("PRO")
        pro_badge.setProperty("class", "proBadge")
        pro_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        pro_badge.style().unpolish(pro_badge)
        pro_badge.style().polish(pro_badge)
        pro_badge.update()

        footer_container = QWidget()
        footer_layout = QHBoxLayout(footer_container)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(6)
        footer_layout.addStretch()
        footer_layout.addWidget(copyright_label)
        footer_layout.addWidget(pro_badge)
        footer_layout.addStretch()

        right_layout.addStretch()
        right_layout.addWidget(footer_container)

        main_layout.addWidget(right_panel, 2)
        self.statusBar().showMessage(self.tr("status_ready"))
        self.log(self.tr("log_startup"))
        # Mostra painel de tradução em tempo real apenas na aba de Tradução
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.on_tab_changed(self.tabs.currentIndex())
        self._apply_theme_panels()
        self._refresh_theme_styles()
        self._update_action_states()

    def create_extraction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        neutral_button_style = self._get_neutral_button_style()
        primary_button_style = self._get_primary_button_style()

        # 1. GRUPO DE PLATAFORMA
        platform_group = QGroupBox(self.tr("platform"))
        platform_group.setObjectName("platform_group")
        platform_layout = QHBoxLayout()
        self.platform_combo = QComboBox()
        self.platform_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.platform_combo.view().setCursor(Qt.CursorShape.PointingHandCursor)
        self.platform_combo.setMinimumHeight(30)  # Altura padrão desktop
        self.platform_combo.setMaxVisibleItems(12)
        self.platform_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        # Mantém a scrollbar do combo no mesmo tamanho das demais
        self.platform_combo.view().setMinimumWidth(0)
        try:
            self.platform_combo.view().verticalScrollBar().setFixedWidth(8)
        except Exception:
            pass
        self.platform_combo.setToolTip(self.tr("tooltip_platform"))
        first_ready_index = -1
        for platform_name, data in ProjectConfig.PLATFORMS.items():
            platform_code = data.get("code", "")
            is_ready = data.get("ready", False)
            if platform_code == "separator":
                self.platform_combo.addItem(platform_name)
                item = self.platform_combo.model().item(
                    self.platform_combo.count() - 1
                )
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                continue
            display_name = platform_name
            if not is_ready:
                display_name = f"{platform_name} (Em breve)"
            self.platform_combo.addItem(display_name, platform_code)
            if is_ready and first_ready_index == -1:
                first_ready_index = self.platform_combo.count() - 1
        # Seleciona primeiro item habilitado (Master System)
        if first_ready_index >= 0:
            self.platform_combo.setCurrentIndex(first_ready_index)
        # Itens "Em breve": apenas cinza + tooltip (selecionáveis)
        for i in range(self.platform_combo.count()):
            t = self.platform_combo.itemText(i)
            if not self._is_supported_platform(t):
                self.platform_combo.setItemData(
                    i, QColor("#8A8A8A"), Qt.ItemDataRole.ForegroundRole
                )
                self.platform_combo.setItemData(
                    i,
                    "Em breve (sem suporte na V1)",
                    Qt.ItemDataRole.ToolTipRole,
                )
        self.platform_combo.currentIndexChanged.connect(self.on_platform_changed)
        platform_layout.addWidget(self.platform_combo)
        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 1.5. AVISO "EM FASE DE TESTES"
        self.console_warning_widget = QWidget()
        console_warning_layout = QVBoxLayout(self.console_warning_widget)
        console_warning_layout.setContentsMargins(0, 10, 0, 10)
        self.console_warning_label = QLabel("🚧 " + self.tr("in_development"))
        self.console_warning_label.setStyleSheet(
            "background-color: #3a3a3a; color: #e0e0e0; font-size: 12pt; font-weight: bold; padding: 10px; border-radius: 6px;"
        )
        self.console_warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        console_warning_layout.addWidget(self.console_warning_label)
        self.console_warning_text = QLabel(self.tr("platform_tooltip"))
        self.console_warning_text.setStyleSheet(
            "background-color: #2f2f2f; color: #cfcfcf; font-size: 10pt; padding: 8px; border-radius: 6px;"
        )
        self.console_warning_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.console_warning_text.setWordWrap(True)
        console_warning_layout.addWidget(self.console_warning_text)
        self.console_warning_widget.setVisible(False)
        layout.addWidget(self.console_warning_widget)

        # 2. GRUPO DE ARQUIVO ROM/JOGO
        rom_group = QGroupBox(self.tr("rom_file"))
        rom_group.setObjectName("rom_file_group")
        rom_layout = QVBoxLayout()

        rom_select_layout = QHBoxLayout()

        # --- CORREÇÃO DE SEMÂNTICA: Laranja/Amarelo quando vazio (Atenção) ---
        self.rom_path_label = QLabel(self.tr("no_rom"))
        self.rom_path_label.setObjectName("rom_path_label")
        self.rom_path_label.setStyleSheet(
            "color: #b0b0b0; font-weight: bold;"
        )  # Neutro
        self.rom_path_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        rom_select_layout.addWidget(self.rom_path_label)

        self.select_rom_btn = QPushButton(self.tr("select_rom"))
        self.select_rom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_rom_btn.setMinimumHeight(36)
        self.select_rom_btn.setMinimumWidth(260)
        self.select_rom_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.select_rom_btn.setToolTip(self.tr("tooltip_select_rom_btn"))
        self.select_rom_btn.clicked.connect(self.select_rom)

        rom_select_layout.addWidget(self.select_rom_btn)
        rom_layout.addLayout(rom_select_layout)

        # PAINEL DE ANÁLISE FORENSE
        self.forensic_analysis_btn = QPushButton(self.tr("forensic_analysis"))
        self.forensic_analysis_btn.setObjectName("forensic_analysis_btn")
        self.forensic_analysis_btn.setMinimumHeight(30)  # Mais compacto
        self.forensic_analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forensic_analysis_btn.setToolTip(self.tr("tooltip_forensic_analysis"))
        self.forensic_analysis_btn.setStyleSheet(neutral_button_style)
        self.forensic_analysis_btn.setEnabled(False)
        self.forensic_analysis_btn.clicked.connect(self.run_forensic_analysis)
        rom_layout.addWidget(self.forensic_analysis_btn)

        self.forensic_progress = QProgressBar()
        self.forensic_progress.setVisible(False)
        self.forensic_progress.setRange(0, 0)  # Indeterminado
        rom_layout.addWidget(self.forensic_progress)

        # VISOR COM BARRA DE ROLAGEM PRETA
        self.engine_detection_scroll = QScrollArea()
        self.engine_detection_scroll.setWidgetResizable(True)
        self.engine_detection_scroll.setMinimumHeight(400)
        self.engine_detection_scroll.setMaximumHeight(400)

        # Barra de rolagem sempre visível
        self.engine_detection_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.engine_detection_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.engine_detection_scroll.setStyleSheet(
            """
            QScrollArea {
                border-radius: 6px;
            }
        """
        )
        self.engine_detection_label = QLabel(self.tr("waiting_file_selection"))
        self.engine_detection_label.setWordWrap(True)
        self.engine_detection_label.setTextFormat(Qt.TextFormat.RichText)
        self.engine_detection_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.engine_detection_label.setMinimumHeight(
            600
        )  # Força o label a ter altura mínima maior
        self.engine_detection_label.setStyleSheet("color: #777; padding: 10px;")
        self.engine_detection_scroll.setWidget(self.engine_detection_label)
        rom_layout.addWidget(self.engine_detection_scroll)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        # 4. BOTÕES DE AÇÃO (CORRIGIDOS PARA DESKTOP SIZE)
        # Altura reduzida de 55 para 40px. Fonte de 14pt para 12pt.

        # # 4. BOTÕES DE AÇÃO (ATUALIZADOS v6.0)
        buttons_h_layout = QHBoxLayout()
        self.select_rom_btn.setStyleSheet(neutral_button_style)

        # Botão Extrair Texto da ROM
        self.extract_btn = QPushButton(self.tr("extract_texts"))
        self.extract_btn.setObjectName("extract_btn")
        self.extract_btn.setMinimumHeight(40)
        self.extract_btn.setStyleSheet(neutral_button_style)
        self.extract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.extract_btn.setToolTip(self.tr("tooltip_extract_texts"))
        self.btn_extrair = self.extract_btn
        self.btn_extrair.setProperty("class", "primary")
        self.btn_extrair.style().unpolish(self.btn_extrair)
        self.btn_extrair.style().polish(self.btn_extrair)
        self.btn_extrair.update()
        self.extract_btn.clicked.connect(self.extract_texts)
        buttons_h_layout.addWidget(self.extract_btn)

        # Botão Prova ASCII (HUD/Intro)
        self.ascii_probe_btn = QPushButton(self.tr("ascii_probe"))
        self.ascii_probe_btn.setObjectName("ascii_probe_btn")
        self.ascii_probe_btn.setMinimumHeight(40)
        self.ascii_probe_btn.setStyleSheet(neutral_button_style)
        self.ascii_probe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ascii_probe_btn.setToolTip(self.tr("tooltip_ascii_probe"))
        self.ascii_probe_btn.setEnabled(False)
        self.ascii_probe_btn.clicked.connect(self.run_ascii_probe)
        buttons_h_layout.addWidget(self.ascii_probe_btn)
        # Oculta opções avançadas para simplificar a interface
        self.ascii_probe_btn.setVisible(False)

        # Botão Carregar Arquivo TXT Extraído
        self.load_txt_btn = QPushButton(self.tr("load_extracted_txt"))
        self.load_txt_btn.setObjectName("load_txt_btn")
        self.load_txt_btn.setMinimumHeight(40)
        self.load_txt_btn.setStyleSheet(neutral_button_style)
        self.load_txt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_txt_btn.setToolTip(self.tr("tooltip_load_extracted_txt"))
        self.load_txt_btn.clicked.connect(self.load_extracted_txt_directly)
        buttons_h_layout.addWidget(self.load_txt_btn)
        # Oculta opções avançadas para simplificar a interface
        self.load_txt_btn.setVisible(False)

        layout.addLayout(buttons_h_layout)

        self.load_txt_hint_label = QLabel(self.tr("hint_load_extracted_txt"))
        self.load_txt_hint_label.setObjectName("load_txt_hint_label")
        self.load_txt_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_txt_hint_label.setStyleSheet("color: #8a8a8a; font-size: 9pt;")
        layout.addWidget(self.load_txt_hint_label)

        # Modo Cobertura Total (Forense)
        self.max_extract_cb = QCheckBox(self.tr("max_extraction_label"))
        self.max_extract_cb.setObjectName("max_extract_cb")
        self.max_extract_cb.setChecked(self.max_extraction_mode)
        self.max_extract_cb.setToolTip(self.tr("tooltip_max_extraction"))
        self.max_extract_cb.setStyleSheet("color: #cfcfcf; font-size: 9pt;")
        if self.max_extraction_locked:
            self.max_extract_cb.setChecked(True)
            self.max_extract_cb.setEnabled(False)
            self.max_extract_cb.setToolTip(self.tr("tooltip_max_extraction_locked"))
        self.max_extract_cb.stateChanged.connect(self._on_max_extraction_changed)
        layout.addWidget(self.max_extract_cb)

        # Botão Otimizar Dados (Laranja)
        self.optimize_btn = QPushButton(self.tr("optimize_data"))
        self.optimize_btn.setObjectName("optimize_btn")
        self.optimize_btn.setMinimumHeight(40)
        self.optimize_btn.setStyleSheet(neutral_button_style)
        self.optimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.optimize_btn.setToolTip(self.tr("tooltip_optimize_data"))
        self.optimize_btn.clicked.connect(
            self.optimize_data
        )  # Conectado ao seu método existente
        layout.addWidget(self.optimize_btn)

        # (Ajuda rápida removida - agora fica no menu superior "Ajuda")

        # 5. BARRAS DE PROGRESSO
        progress_bar_style = self._get_progress_bar_style()
        self.forensic_progress.setStyleSheet(progress_bar_style)
        self.extract_progress_bar = QProgressBar()
        self.extract_progress_bar.setFormat(
            f"{self.tr('extraction_progress')}: %p%"
        )
        self.extract_progress_bar.setFixedHeight(20)  # Barra fina e elegante
        self.extract_progress_bar.setStyleSheet(progress_bar_style)
        layout.addWidget(self.extract_progress_bar)

        self.optimize_progress_bar = QProgressBar()
        self.optimize_progress_bar.setFormat(
            f"{self.tr('optimization_progress')}: %p%"
        )
        self.optimize_progress_bar.setFixedHeight(20)
        self.optimize_progress_bar.setStyleSheet(progress_bar_style)
        layout.addWidget(self.optimize_progress_bar)

        self.extract_status_label = QLabel(self.tr("waiting"))
        self.extract_status_label.setObjectName("extract_status_label")
        self.extract_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extract_status_label.setStyleSheet("color: #777; font-size: 9pt;")
        layout.addWidget(self.extract_status_label)

        self.optimize_status_label = QLabel(self.tr("waiting"))
        self.optimize_status_label.setObjectName("optimize_status_label")
        self.optimize_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.optimize_status_label.setStyleSheet("color: #777; font-size: 9pt;")
        layout.addWidget(self.optimize_status_label)

        layout.addStretch()
        return widget

    def create_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        neutral_button_style = self._get_neutral_button_style()
        primary_button_style = self._get_primary_button_style()

        file_group = QGroupBox(self.tr("file_to_translate"))
        file_group.setObjectName("file_to_translate_group")
        file_layout = QHBoxLayout()

        # Semântica: Cinza/Amarelo quando vazio
        self.trans_file_label = QLabel(self.tr("no_file"))
        self.trans_file_label.setObjectName("trans_file_label")
        self.trans_file_label.setStyleSheet("color: #b0b0b0;")
        file_layout.addWidget(self.trans_file_label)

        self.sel_file_btn = QPushButton(self.tr("select_file"))
        self.sel_file_btn.setMinimumHeight(36)
        self.sel_file_btn.setMinimumWidth(260)
        self.sel_file_btn.setObjectName("sel_file_btn")
        self.sel_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sel_file_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.sel_file_btn.setStyleSheet(neutral_button_style)
        self.sel_file_btn.setToolTip(self.tr("tooltip_select_translation_file"))
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
        self.source_lang_combo.currentTextChanged.connect(
            self.on_source_language_changed
        )
        self.target_lang_combo.currentTextChanged.connect(
            self.on_target_language_changed
        )
        lang_config_group.setLayout(lang_config_layout)
        layout.addWidget(lang_config_group)

        mode_group = QGroupBox(self.tr("translation_mode"))
        mode_group.setObjectName("mode_group")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_combo.addItems(
            [
                "🤖 AUTO (Gemini + Ollama)",
                "⚡ Gemini (Google AI)",
                "🦙 Llama (Ollama Local)",
                "🤖 ChatGPT (OpenAI)",
            ]
        )
        self.mode_combo.setCurrentIndex(0)  # AUTO como padrão
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
        api_container.setMinimumHeight(30)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setMinimumHeight(28)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.eye_btn = QToolButton()
        self.btn_toggle_api = self.eye_btn
        self.btn_toggle_api.setText("👁")
        self.btn_toggle_api.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.btn_toggle_api.setIconSize(QSize(16, 16))
        self.btn_toggle_api.setMinimumSize(28, 28)
        self.btn_toggle_api.setMaximumSize(28, 28)
        self.btn_toggle_api.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.btn_toggle_api.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_api.pressed.connect(self._eye_show_key)
        self.btn_toggle_api.released.connect(self._eye_hide_key)
        theme = self._get_theme_colors()
        btn_hover = (
            QColor(theme["button"]).lighter(110).name()
            if self.current_theme != "Preto (Black)"
            else theme["button"]
        )
        eye_btn_style = (
            neutral_button_style.replace("QPushButton", "QToolButton")
            + f"""
            QToolButton {{ padding: 0px; font-size: 11pt; }}
            QToolButton:hover {{ background: {btn_hover}; border-radius: 6px; }}
        """
        )
        self.eye_btn.setStyleSheet(eye_btn_style)
        self.eye_btn.setFont(QFont("Segoe UI Emoji", 11))
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
        self.clear_cache_btn = QPushButton(self.tr("clear_cache"))
        self.clear_cache_btn.setObjectName("clear_cache_btn")
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.setFixedHeight(28)
        self.clear_cache_btn.setStyleSheet(neutral_button_style)
        self.clear_cache_btn.setToolTip(
            self.tr("clear_cache_tooltip")
        )
        self.clear_cache_btn.clicked.connect(self.clear_translation_cache)
        api_layout.addWidget(self.clear_cache_btn, 3, 1)

        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)

        translation_progress_group = QGroupBox(self.tr("translation_progress"))
        translation_progress_group.setObjectName("translation_progress_group")
        translation_progress_layout = QVBoxLayout()
        self.translation_progress_bar = QProgressBar()
        self.translation_progress_bar.setFormat(
            f"{self.tr('translation_progress')}: %p%"
        )
        self.translation_progress_bar.setFixedHeight(20)
        self.translation_progress_bar.setStyleSheet(self._get_progress_bar_style())
        translation_progress_layout.addWidget(self.translation_progress_bar)
        self.translation_status_label = QLabel(self.tr("waiting"))
        self.translation_status_label.setObjectName("translation_status_label")
        self.translation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_status_label.setStyleSheet("color: #777; font-size: 9pt;")
        translation_progress_layout.addWidget(self.translation_status_label)
        translation_progress_group.setLayout(translation_progress_layout)
        layout.addWidget(translation_progress_group)

        # Botão diagnóstico gráfico (aparece somente se houver needs_review_gfx)
        self.export_gfx_diag_btn = QPushButton("Exportar diagnóstico gráfico")
        self.export_gfx_diag_btn.setObjectName("export_gfx_diag_btn")
        self.export_gfx_diag_btn.setMinimumHeight(32)
        self.export_gfx_diag_btn.setStyleSheet(neutral_button_style)
        self.export_gfx_diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_gfx_diag_btn.setVisible(False)
        self.export_gfx_diag_btn.clicked.connect(self.export_gfx_diagnostic)
        layout.addWidget(self.export_gfx_diag_btn)

        # Botão TRADUZIR (Tamanho 40px)
        self.translate_btn = QPushButton(self.tr("translate_ai"))
        self.translate_btn.setObjectName("translate_btn")
        self.translate_btn.setMinimumHeight(40)  # Ajustado
        self.translate_btn.setStyleSheet(neutral_button_style)
        self.translate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.translate_btn.setToolTip(self.tr("tooltip_translate_ai"))
        def _apply_btn_class(btn, cls):
            btn.setProperty("class", cls)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

        _apply_btn_class(self.translate_btn, "primaryOutline")
        self.translate_btn.clicked.connect(self.translate_texts)
        layout.addWidget(self.translate_btn)

        # Botão PARAR (Tamanho 40px)
        self.stop_translation_btn = QPushButton(self.tr("stop_translation"))
        self.stop_translation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_translation_btn.setObjectName("stop_translation_btn")
        self.stop_translation_btn.setMinimumHeight(40)  # Ajustado
        self.stop_translation_btn.setStyleSheet(neutral_button_style)
        self.stop_translation_btn.setToolTip(self.tr("tooltip_stop_translation"))
        _apply_btn_class(self.stop_translation_btn, "dangerOutline")
        self.stop_translation_btn.clicked.connect(self.stop_translation)
        self.stop_translation_btn.setEnabled(False)
        layout.addWidget(self.stop_translation_btn)

        layout.addStretch()
        return widget

    def create_reinsertion_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        rom_group = QGroupBox(self.tr("original_rom"))
        rom_group.setObjectName("reinsert_rom_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()

        self.reinsert_rom_label = QLabel(self.tr("no_rom"))
        self.reinsert_rom_label.setObjectName("reinsert_rom_label")
        self.reinsert_rom_label.setStyleSheet("color: #b0b0b0;")  # Neutro
        self.reinsert_rom_label.setMinimumWidth(0)
        self.reinsert_rom_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        rom_select_layout.addWidget(self.reinsert_rom_label)

        self.select_reinsert_rom_btn = QPushButton(self.tr("select_rom"))
        self.select_reinsert_rom_btn.setObjectName("select_reinsert_rom_btn")
        self.select_reinsert_rom_btn.setMinimumHeight(36)
        self.select_reinsert_rom_btn.setMinimumWidth(260)
        self.select_reinsert_rom_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.select_reinsert_rom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_reinsert_rom_btn.setToolTip(self.tr("tooltip_select_reinsert_rom"))
        self.select_reinsert_rom_btn.clicked.connect(self.select_rom_for_reinsertion)
        rom_select_layout.addWidget(self.select_reinsert_rom_btn)
        rom_layout.addLayout(rom_select_layout)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        trans_group = QGroupBox(self.tr("translated_file"))
        trans_group.setObjectName("translated_file_group")
        trans_layout = QVBoxLayout()
        trans_select_layout = QHBoxLayout()

        self.translated_file_label = QLabel(self.tr("no_rom"))
        self.translated_file_label.setObjectName("translated_file_label")
        self.translated_file_label.setStyleSheet("color: #b0b0b0;")  # Neutro
        self.translated_file_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        trans_select_layout.addWidget(self.translated_file_label)

        self.select_translated_btn = QPushButton(self.tr("select_file"))
        self.select_translated_btn.setObjectName("select_translated_btn")
        self.select_translated_btn.setMinimumHeight(36)
        self.select_translated_btn.setMinimumWidth(260)
        self.select_translated_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.select_translated_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_translated_btn.setToolTip(self.tr("tooltip_select_translated_file"))
        self.select_translated_btn.clicked.connect(self.select_translated_file)
        trans_select_layout.addWidget(self.select_translated_btn)
        trans_layout.addLayout(trans_select_layout)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        output_group = QGroupBox(self.tr("output_rom"))
        output_group.setObjectName("output_rom_group")
        output_layout = QVBoxLayout()
        self.output_rom_edit = QLineEdit()
        self.output_rom_edit.setPlaceholderText(self._build_output_placeholder(None))
        self.output_rom_edit.setToolTip(
            self.tr("output_rom_tooltip")
        )
        output_layout.addWidget(self.output_rom_edit)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Opções avançadas de reinserção
        self.force_blocked_checkbox = QCheckBox(self.tr("force_blocked_label"))
        self.force_blocked_checkbox.setObjectName("force_blocked_checkbox")
        self.force_blocked_checkbox.setToolTip(
            self.tr("force_blocked_tooltip")
        )
        layout.addWidget(self.force_blocked_checkbox)

        reinsertion_progress_group = QGroupBox(self.tr("reinsertion_progress"))
        reinsertion_progress_group.setObjectName("reinsertion_progress_group")
        reinsertion_progress_layout = QVBoxLayout()
        self.reinsertion_progress_bar = QProgressBar()
        self.reinsertion_progress_bar.setFormat(
            f"{self.tr('reinsertion_progress')}: %p%"
        )
        self.reinsertion_progress_bar.setFixedHeight(20)
        self.reinsertion_progress_bar.setStyleSheet(self._get_progress_bar_style())
        reinsertion_progress_layout.addWidget(self.reinsertion_progress_bar)
        self.reinsertion_status_label = QLabel(self.tr("waiting"))
        self.reinsertion_status_label.setObjectName("reinsertion_status_label")
        self.reinsertion_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reinsertion_status_label.setStyleSheet("color: #777; font-size: 9pt;")
        reinsertion_progress_layout.addWidget(self.reinsertion_status_label)
        reinsertion_progress_group.setLayout(reinsertion_progress_layout)
        layout.addWidget(reinsertion_progress_group)

        neutral_button_style = self._get_neutral_button_style()
        primary_button_style = self._get_primary_button_style()

        self.select_reinsert_rom_btn.setStyleSheet(neutral_button_style)
        self.select_translated_btn.setStyleSheet(neutral_button_style)

        self.reinsert_btn = QPushButton(self.tr("reinsert"))
        self.reinsert_btn.setObjectName("reinsert_btn")
        self.reinsert_btn.setMinimumHeight(40)  # Ajustado
        self.reinsert_btn.setStyleSheet(neutral_button_style)
        self.reinsert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reinsert_btn.setToolTip(self.tr("tooltip_reinsert"))
        self.reinsert_btn.setProperty("class", "primary")
        self.reinsert_btn.style().unpolish(self.reinsert_btn)
        self.reinsert_btn.style().polish(self.reinsert_btn)
        self.reinsert_btn.update()
        self.reinsert_btn.clicked.connect(self.reinsert)
        layout.addWidget(self.reinsert_btn)

        layout.addStretch()
        return widget

    def _build_output_placeholder(self, base_name: str | None) -> str:
        if not base_name or base_name == "jogo_PTBR":
            base_name = self.tr("output_placeholder_name")
        return self.tr("output_placeholder").format(name=base_name)

    def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ui_lang_group = QGroupBox(self.tr("ui_language"))
        ui_lang_group.setObjectName("ui_lang_group")
        ui_lang_layout = QHBoxLayout()
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setCursor(
            Qt.CursorShape.PointingHandCursor
        )  # Cursor de mãozinha
        self.ui_lang_combo.setMaxVisibleItems(15)
        self.ui_lang_combo.addItems(ProjectConfig.UI_LANGUAGES.keys())
        self.ui_lang_combo.setCurrentText(
            self._get_ui_lang_label(self.current_ui_lang)
        )  # Define idioma inicial
        self.ui_lang_combo.currentTextChanged.connect(self.change_ui_language)
        ui_lang_layout.addWidget(self.ui_lang_combo)
        ui_lang_group.setLayout(ui_lang_layout)
        layout.addWidget(ui_lang_group)

        theme_group = QGroupBox(self.tr("theme"))
        theme_group.setObjectName("theme_group")
        theme_layout = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.setCursor(
            Qt.CursorShape.PointingHandCursor
        )  # Cursor de mãozinha
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
        self.font_combo.setCursor(
            Qt.CursorShape.PointingHandCursor
        )  # Cursor de mãozinha
        self.font_combo.addItems(ProjectConfig.FONT_FAMILIES.keys())
        self.font_combo.setCurrentText(self.current_font_family)
        self.font_combo.currentTextChanged.connect(self.change_font_family)
        font_layout.addWidget(self.font_combo)
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        mode_group = QGroupBox(self.tr("usage_mode"))
        mode_group.setObjectName("usage_mode_group")
        mode_layout = QVBoxLayout()
        self.beginner_mode_cb = QCheckBox(self.tr("beginner_mode_label"))
        self.beginner_mode_cb.setObjectName("beginner_mode_cb")
        self.beginner_mode_cb.setChecked(True)
        self.beginner_mode_cb.setToolTip(self.tr("beginner_mode_tip"))
        self.beginner_mode_cb.setStyleSheet("QCheckBox { font-size: 9pt; }")
        self.beginner_mode_cb.setEnabled(False)
        self.beginner_mode_cb.stateChanged.connect(self._on_beginner_mode_changed)
        mode_layout.addWidget(self.beginner_mode_cb)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # PROFESSIONAL: Version label for buyer confidence
        layout.addStretch()
        self.version_label = QLabel(
            self.tr("version_label").format(version="v5.3 Stable")
        )
        self.version_label.setStyleSheet(
            "color: #888; font-size: 9pt; font-style: italic;"
        )
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        return widget

    # NOTE: create_graphics_lab_tab() has been moved to gui_tabs/graphic_lab.py

    def on_mode_changed(self, index: int):
        # Esconde API key apenas para Ollama Local (index 2)
        self.api_group.setVisible(index != 2)

    def keyPressEvent(self, event):
        """
        Intercepta eventos de teclado.
        Graphics Lab navigation is now handled by the GraphicLabTab itself.
        """
        # Delegate to graphics tab if it's the active tab
        if hasattr(self, "tabs") and self.tabs.currentWidget() == self.graphics_lab_tab:
            if self.graphics_lab_tab and hasattr(
                self.graphics_lab_tab, "keyPressEvent"
            ):
                self.graphics_lab_tab.keyPressEvent(event)
                return

        # Chama implementação padrão para outras teclas
        super().keyPressEvent(event)

    def populate_manual_combo(self):
        """Populate manual dropdown with translated items using logical IDs."""
        if not hasattr(self, "manual_combo") or self.manual_combo is None:
            return
        # Temporarily disconnect signal to prevent accidental auto-opening
        try:
            self.manual_combo.currentIndexChanged.disconnect(self.show_manual_step)
            signal_was_connected = True
        except (TypeError, RuntimeError):
            signal_was_connected = False

        # Repopulate combo (apenas funcionalidades ativas)
        self.manual_combo.clear()
        self.manual_combo.addItems(
            [
                self.tr("manual_guide_title"),
                self.tr("manual_step_1"),
                self.tr("manual_step_2"),
                self.tr("manual_step_3"),
                self.tr("manual_step_4"),
                # "Laboratório Gráfico" e "Jogos de PC" removidos - em desenvolvimento
            ]
        )

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
                if k in selected_text:
                    data = v
                    break

        # Se for separador ou inválido, desativa
        if not data or data.get("code") == "separator":
            if hasattr(self, "extract_btn"):
                self.extract_btn.setEnabled(False)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
            return

        is_ready = data.get("ready", False)

        # Mostrar/ocultar aviso de plataforma em desenvolvimento
        if hasattr(self, "console_warning_widget"):
            self.console_warning_widget.setVisible(not is_ready)

        if hasattr(self, "extract_btn"):
            if is_ready:
                # PLATAFORMA PRONTA
                self.extract_btn.setEnabled(True)
                self.extract_btn.setText(self.tr("extract_texts"))
                self.extract_btn.setToolTip("")
                if hasattr(self, "optimize_btn"):
                    self.optimize_btn.setEnabled(True)
                if hasattr(self, "select_rom_btn"):
                    self.select_rom_btn.setEnabled(True)
                if hasattr(self, "forensic_analysis_btn"):
                    self.forensic_analysis_btn.setEnabled(True)
                if hasattr(self, "ascii_probe_btn"):
                    self.ascii_probe_btn.setEnabled(True)
                self.log(f"[OK] Plataforma selecionada: {selected_text}")
            else:
                # PLATAFORMA EM FASE DE TESTES
                self.extract_btn.setEnabled(False)
                # Texto do Botão (Usa tradução)
                self.extract_btn.setText("🚧 " + self.tr("in_development"))
                # Tooltip ao passar o mouse (Usa tradução)
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))

                if hasattr(self, "optimize_btn"):
                    self.optimize_btn.setEnabled(False)
                    self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

                if hasattr(self, "select_rom_btn"):
                    self.select_rom_btn.setEnabled(False)

                if hasattr(self, "forensic_analysis_btn"):
                    self.forensic_analysis_btn.setEnabled(False)
                if hasattr(self, "ascii_probe_btn"):
                    self.ascii_probe_btn.setEnabled(False)

        self._update_action_states()

    def on_platform_changed(self, index=None):
        """Garante seleção livre, mas bloqueia ações fora do suporte V1."""
        self.on_platform_selected(index)
        selected_text = (
            self.platform_combo.currentText() if hasattr(self, "platform_combo") else ""
        )
        if not selected_text:
            return
        data = ProjectConfig.PLATFORMS.get(selected_text)
        if not data:
            for k, v in ProjectConfig.PLATFORMS.items():
                if k in selected_text:
                    data = v
                    break
        if not data or data.get("code") == "separator":
            return
        is_ready = data.get("ready", False)
        if not is_ready:
            if hasattr(self, "extract_btn"):
                self.extract_btn.setEnabled(False)
            if hasattr(self, "translate_btn"):
                self.translate_btn.setEnabled(False)
            if hasattr(self, "reinsert_btn"):
                self.reinsert_btn.setEnabled(False)
            self._log_info_once(
                "Plataforma em breve. V1 suporta apenas Master System.",
                key="platform_unsupported",
            )

    def on_tab_changed(self, index: int):
        """Mostra o painel de tradução em tempo real somente na aba de Tradução."""
        if hasattr(self, "realtime_group"):
            self.realtime_group.setVisible(index == 2)
        if (
            hasattr(self, "graphics_lab_tab")
            and self.graphics_lab_tab
            and hasattr(self, "tabs")
            and self.tabs.widget(index) == self.graphics_lab_tab
        ):
            if hasattr(self.graphics_lab_tab, "auto_scan_and_ocr"):
                QTimer.singleShot(100, self.graphics_lab_tab.auto_scan_and_ocr)

    def change_ui_language(self, lang_name: str):
        try:
            def _normalize_label(label: str) -> str:
                if not label:
                    return ""
                # remove regional indicator symbols (flags)
                cleaned = "".join(
                    ch for ch in label if not (0x1F1E6 <= ord(ch) <= 0x1F1FF)
                )
                # remove leading country code like "BR " or "US "
                cleaned = re.sub(r"^[A-Z]{2}\s+", "", cleaned)
                return cleaned.strip().lower()

            code = ProjectConfig.UI_LANGUAGES.get(lang_name)
            if not code:
                target_norm = _normalize_label(lang_name)
                for key, val in ProjectConfig.UI_LANGUAGES.items():
                    if _normalize_label(key) == target_norm:
                        code = val
                        break
            if not code:
                self.log(f"[WARN] Idioma não encontrado: {lang_name}")
                return

            self.current_ui_lang = code
            self.apply_layout_direction()
            self.refresh_ui_labels()
            self.save_config()
            if not getattr(self, "_startup", False):
                self.log(f"[LANG] UI language: {self._format_lang_for_log()}")
        except Exception as e:
            self.log(f"[ERROR] Falha ao trocar idioma: {_sanitize_error(e)}")

    def refresh_ui_labels(self):
        """Atualiza a interface gráfica quando o idioma é alterado."""
        self.update_window_title()
        if hasattr(self, "statusBar"):
            try:
                self.statusBar().showMessage(self.tr("status_ready"))
            except Exception:
                pass
        self.setup_menu()

        # Tabs
        self.tabs.setTabText(0, self._clean_tab_label(self.tr("tab1")))  # Extração
        self.tabs.setTabText(
            1, self._clean_tab_label(self.tr("tab2"))
        )  # Laboratório Gráfico
        self.tabs.setTabText(2, self._clean_tab_label(self.tr("tab3")))  # Tradução
        self.tabs.setTabText(3, self._clean_tab_label(self.tr("tab4")))  # Reinserção
        self.tabs.setTabText(
            4, self._clean_tab_label(self.tr("tab5"))
        )  # Configurações

        # Atualiza cabeçalho do log e botão
        if hasattr(self, "log_title_label"):
            self.log_title_label.setText(self.tr("log"))
        if hasattr(self, "log_group") and hasattr(self, "log_toggle_btn"):
            self.log_toggle_btn.setText(
                self.tr("log_hide")
                if self.log_group.isVisible()
                else self.tr("log_show")
            )

        # ═══════════════════════════════════════════════════════════
        # GRAPHICS LAB UI UPDATES (Tab 4 - i18n Support)
        # ═══════════════════════════════════════════════════════════

        # Atualizar a aba gráfica (se existir)
        graphics_tab = getattr(self, "graphics_lab_tab", None)
        if graphics_tab and hasattr(graphics_tab, "retranslate"):
            graphics_tab.retranslate()

        # Update theme combo with translated names
        if hasattr(self, "theme_combo"):
            # Temporarily disconnect to avoid triggering change event
            try:
                self.theme_combo.currentTextChanged.disconnect(self.change_theme)
            except (TypeError, RuntimeError):
                pass
            # Clear and repopulate with translated names
            self.theme_combo.clear()
            self.theme_combo.addItems(self.get_all_translated_theme_names())
            # Restore current selection with translated name
            current_translated = self.get_translated_theme_name(self.current_theme)
            self.theme_combo.setCurrentText(current_translated)
            # Reconnect the signal
            try:
                self.theme_combo.currentTextChanged.connect(self.change_theme)
            except (TypeError, RuntimeError):
                pass

        # Update output ROM placeholder with full extension list
        if hasattr(self, "output_rom_edit"):
            self.output_rom_edit.setPlaceholderText(
                self._build_output_placeholder(None)
            )

        # Update source language combo with translated AUTO-DETECT
        if hasattr(self, "source_lang_combo"):
            self._suppress_lang_logs = True
            self.source_lang_combo.blockSignals(True)
            current_index = self.source_lang_combo.currentIndex()
            self.source_lang_combo.clear()
            self.source_lang_combo.addItems(self.get_all_translated_source_languages())
            self.source_lang_combo.setCurrentIndex(current_index)
            self.source_lang_combo.blockSignals(False)
            self._suppress_lang_logs = False

        if hasattr(self, "target_lang_combo"):
            self._suppress_lang_logs = True
            self.target_lang_combo.blockSignals(True)
            current_index = self.target_lang_combo.currentIndex()
            self.target_lang_combo.clear()
            self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
            self.target_lang_combo.setCurrentIndex(current_index)
            self.target_lang_combo.blockSignals(False)
            self._suppress_lang_logs = False

        # Atualiza o título do grupo de Ajuda
        if hasattr(self, "help_group"):
            self.help_group.setTitle(self.tr("help_support"))

        # Atualiza o texto do Guia
        if hasattr(self, "manual_label"):
            self.manual_label.setText(self.tr("manual_guide"))
        if hasattr(self, "realtime_group"):
            self.realtime_group.setTitle(self.tr("realtime_group_title"))
        if hasattr(self, "realtime_original_label"):
            self.realtime_original_label.setText(self.tr("realtime_original_label"))
        if hasattr(self, "realtime_translated_label"):
            self.realtime_translated_label.setText(self.tr("realtime_translated_label"))
        if hasattr(self, "realtime_info_label"):
            self.realtime_info_label.setText(self.tr("realtime_info_label"))
        if hasattr(self, "graphics_title_label"):
            self.graphics_title_label.setText(self.tr("graphics_lab_title"))
        if hasattr(self, "graphics_msg_label"):
            self.graphics_msg_label.setText(self.tr("graphics_placeholder_msg"))
        if hasattr(self, "graphics_tech_note"):
            self.graphics_tech_note.setText(self.tr("graphics_tech_note"))
        if hasattr(self, "version_label"):
            self.version_label.setText(
                self.tr("version_label").format(version="v5.3 Stable")
            )
        if hasattr(self, "clear_cache_btn"):
            self.clear_cache_btn.setText(self.tr("clear_cache"))
            self.clear_cache_btn.setToolTip(self.tr("clear_cache_tooltip"))
        if hasattr(self, "output_rom_edit"):
            self.output_rom_edit.setToolTip(self.tr("output_rom_tooltip"))
        if hasattr(self, "force_blocked_checkbox"):
            self.force_blocked_checkbox.setToolTip(self.tr("force_blocked_tooltip"))

        def safe_update(object_name, widget_type, update_func):
            widget = self.findChild(widget_type, object_name)
            if widget:
                update_func(widget)

        # Manual dropdown
        if hasattr(self, "populate_manual_combo"):
            self.populate_manual_combo()

        # Platform roadmap - REMOVED (not important for users)
        # if self.platform_combo and self.platform_combo.count() > 0:
        #     last_index = self.platform_combo.count() - 1
        #     self.platform_combo.setItemText(last_index, "📋 " + self.tr("roadmap_item"))

        # Buttons
        safe_update(
            "btn_extract", QPushButton, lambda w: w.setText(self.tr("btn_extract"))
        )
        safe_update(
            "btn_optimize", QPushButton, lambda w: w.setText(self.tr("btn_optimize"))
        )
        safe_update(
            "stop_translation_btn",
            QPushButton,
            lambda w: w.setText(self.tr("stop_translation")),
        )
        safe_update(
            "reinsert_btn", QPushButton, lambda w: w.setText(self.tr("reinsert"))
        )
        safe_update(
            "extract_btn", QPushButton, lambda w: w.setText(self.tr("extract_texts"))
        )
        safe_update(
            "optimize_btn", QPushButton, lambda w: w.setText(self.tr("optimize_data"))
        )
        safe_update(
            "forensic_analysis_btn",
            QPushButton,
            lambda w: w.setText(self.tr("forensic_analysis")),
        )
        safe_update(
            "ascii_probe_btn", QPushButton, lambda w: w.setText(self.tr("ascii_probe"))
        )
        safe_update(
            "load_txt_btn",
            QPushButton,
            lambda w: w.setText(self.tr("load_extracted_txt")),
        )
        safe_update(
            "translate_btn", QPushButton, lambda w: w.setText(self.tr("translate_ai"))
        )

        # Groups
        safe_update(
            "platform_group", QGroupBox, lambda w: w.setTitle(self.tr("platform"))
        )
        safe_update(
            "rom_file_group", QGroupBox, lambda w: w.setTitle(self.tr("rom_file"))
        )
        safe_update(
            "extract_progress_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("extraction_progress")),
        )
        safe_update(
            "optimize_progress_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("optimization_progress")),
        )
        safe_update(
            "file_to_translate_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("file_to_translate")),
        )
        safe_update(
            "lang_config_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("language_config")),
        )
        safe_update(
            "mode_group", QGroupBox, lambda w: w.setTitle(self.tr("translation_mode"))
        )
        safe_update("api_group", QGroupBox, lambda w: w.setTitle(self.tr("api_config")))
        safe_update(
            "translation_progress_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("translation_progress")),
        )
        safe_update(
            "reinsert_rom_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("original_rom")),
        )

        # Labels
        safe_update(
            "rom_path_label",
            QLabel,
            lambda w: (
                w.setText(self.tr("no_rom")) if self.original_rom_path is None else None
            ),
        )
        if hasattr(self, "extract_progress_bar"):
            self.extract_progress_bar.setFormat(
                f"{self.tr('extraction_progress')}: %p%"
            )
        if hasattr(self, "optimize_progress_bar"):
            self.optimize_progress_bar.setFormat(
                f"{self.tr('optimization_progress')}: %p%"
            )
        if hasattr(self, "translation_progress_bar"):
            self.translation_progress_bar.setFormat(
                f"{self.tr('translation_progress')}: %p%"
            )
        if hasattr(self, "reinsertion_progress_bar"):
            self.reinsertion_progress_bar.setFormat(
                f"{self.tr('reinsertion_progress')}: %p%"
            )
        if (
            hasattr(self, "engine_detection_label")
            and self.original_rom_path is None
        ):
            self.engine_detection_label.setText(
                self.tr("waiting_file_selection")
            )
        if hasattr(self, "console_warning_label"):
            self.console_warning_label.setText("🚧 " + self.tr("in_development"))
        if hasattr(self, "console_warning_text"):
            self.console_warning_text.setText(self.tr("platform_tooltip"))
        safe_update(
            "extract_status_label", QLabel, lambda w: w.setText(self.tr("waiting"))
        )
        safe_update(
            "optimize_status_label", QLabel, lambda w: w.setText(self.tr("waiting"))
        )
        safe_update(
            "trans_file_label",
            QLabel,
            lambda w: (
                w.setText(self.tr("no_file")) if self.optimized_file is None else None
            ),
        )
        safe_update(
            "source_lang_label", QLabel, lambda w: w.setText(self.tr("source_language"))
        )
        safe_update(
            "target_lang_label", QLabel, lambda w: w.setText(self.tr("target_language"))
        )
        safe_update("api_key_label", QLabel, lambda w: w.setText(self.tr("api_key")))
        safe_update("workers_label", QLabel, lambda w: w.setText(self.tr("workers")))
        safe_update("timeout_label", QLabel, lambda w: w.setText(self.tr("timeout")))
        safe_update(
            "translation_status_label", QLabel, lambda w: w.setText(self.tr("waiting"))
        )

        # Checkboxes
        safe_update("cache_check", QCheckBox, lambda w: w.setText(self.tr("use_cache")))
        safe_update(
            "beginner_mode_cb",
            QCheckBox,
            lambda w: w.setText(self.tr("beginner_mode_label")),
        )
        safe_update(
            "max_extract_cb",
            QCheckBox,
            lambda w: w.setText(self.tr("max_extraction_label")),
        )
        if hasattr(self, "max_extract_cb") and self.max_extraction_locked:
            self.max_extract_cb.setEnabled(False)
            self.max_extract_cb.setToolTip(self.tr("tooltip_max_extraction_locked"))
        safe_update(
            "force_blocked_checkbox",
            QCheckBox,
            lambda w: w.setText(self.tr("force_blocked_label")),
        )

        # Button icons
        if self.select_rom_btn:
            self.select_rom_btn.setText(self.tr("select_rom"))
        if self.sel_file_btn:
            self.sel_file_btn.setText(self.tr("select_file"))

        # Update select reinsert ROM button with folder icon
        safe_update(
            "select_reinsert_rom_btn",
            QPushButton,
            lambda w: w.setText(self.tr("select_rom")),
        )

        safe_update(
            "reinsert_rom_label",
            QLabel,
            lambda w: (
                w.setText(self.tr("no_rom")) if self.original_rom_path is None else None
            ),
        )
        safe_update(
            "translated_file_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("translated_file")),
        )
        safe_update(
            "translated_file_label",
            QLabel,
            lambda w: (
                w.setText(self.tr("no_rom")) if self.translated_file is None else None
            ),
        )

        # Update select translated file button with folder icon
        safe_update(
            "select_translated_btn",
            QPushButton,
            lambda w: w.setText(self.tr("select_file")),
        )
        safe_update(
            "output_rom_group", QGroupBox, lambda w: w.setTitle(self.tr("output_rom"))
        )
        safe_update(
            "usage_mode_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("usage_mode")),
        )
        safe_update(
            "beginner_hint_extraction",
            QLabel,
            lambda w: w.setText(self.tr("beginner_hint_extraction")),
        )
        safe_update(
            "beginner_hint_translation",
            QLabel,
            lambda w: w.setText(self.tr("beginner_hint_translation")),
        )
        safe_update(
            "beginner_hint_reinsert",
            QLabel,
            lambda w: w.setText(self.tr("beginner_hint_reinsert")),
        )
        safe_update(
            "translation_file_help",
            QLabel,
            lambda w: w.setText(self.tr("translation_file_help")),
        )
        safe_update(
            "translation_lang_help",
            QLabel,
            lambda w: w.setText(self.tr("translation_lang_help")),
        )
        safe_update(
            "translation_mode_help",
            QLabel,
            lambda w: w.setText(self.tr("translation_mode_help")),
        )
        safe_update(
            "translation_api_help",
            QLabel,
            lambda w: w.setText(self.tr("translation_api_help")),
        )

        # Tooltips principais (atualiza idioma)
        if hasattr(self, "platform_combo"):
            self.platform_combo.setToolTip(self.tr("tooltip_platform"))
        if hasattr(self, "select_rom_btn"):
            self.select_rom_btn.setToolTip(self.tr("tooltip_select_rom_btn"))
        if hasattr(self, "forensic_analysis_btn"):
            self.forensic_analysis_btn.setToolTip(
                self.tr("tooltip_forensic_analysis")
            )
        if hasattr(self, "ascii_probe_btn"):
            self.ascii_probe_btn.setToolTip(self.tr("tooltip_ascii_probe"))
        if hasattr(self, "max_extract_cb"):
            if self.max_extraction_locked:
                self.max_extract_cb.setToolTip(
                    self.tr("tooltip_max_extraction_locked")
                )
            else:
                self.max_extract_cb.setToolTip(self.tr("tooltip_max_extraction"))
        if hasattr(self, "beginner_mode_cb"):
            self.beginner_mode_cb.setToolTip(self.tr("beginner_mode_tip"))
        if hasattr(self, "load_txt_btn"):
            self.load_txt_btn.setToolTip(self.tr("tooltip_load_extracted_txt"))
        if hasattr(self, "optimize_btn"):
            self.optimize_btn.setToolTip(self.tr("tooltip_optimize_data"))
        if hasattr(self, "sel_file_btn"):
            self.sel_file_btn.setToolTip(self.tr("tooltip_select_translation_file"))
        if hasattr(self, "translate_btn"):
            self.translate_btn.setToolTip(self.tr("tooltip_translate_ai"))
        if hasattr(self, "stop_translation_btn"):
            self.stop_translation_btn.setToolTip(self.tr("tooltip_stop_translation"))
        if hasattr(self, "select_reinsert_rom_btn"):
            self.select_reinsert_rom_btn.setToolTip(
                self.tr("tooltip_select_reinsert_rom")
            )
        if hasattr(self, "select_translated_btn"):
            self.select_translated_btn.setToolTip(
                self.tr("tooltip_select_translated_file")
            )
        if hasattr(self, "reinsert_btn"):
            self.reinsert_btn.setToolTip(self.tr("tooltip_reinsert"))

        safe_update(
            "reinsertion_progress_group",
            QGroupBox,
            lambda w: w.setTitle(self.tr("reinsertion_progress")),
        )
        safe_update(
            "reinsertion_status_label", QLabel, lambda w: w.setText(self.tr("waiting"))
        )

        safe_update(
            "load_txt_hint_label",
            QLabel,
            lambda w: w.setText(self.tr("hint_load_extracted_txt")),
        )

        # Update reinsert button with syringe icon
        safe_update(
            "reinsert_btn",
            QPushButton,
            lambda w: w.setText("💉 " + self.tr("reinsert")),
        )

        # Update tooltips for disabled platform buttons
        if hasattr(self, "extract_btn"):
            current_tooltip = self.extract_btn.toolTip()
            # If button is disabled and has a tooltip, update it
            if not self.extract_btn.isEnabled() and current_tooltip:
                self.extract_btn.setToolTip(self.tr("platform_tooltip"))
        if hasattr(self, "optimize_btn"):
            current_tooltip = self.optimize_btn.toolTip()
            if not self.optimize_btn.isEnabled() and current_tooltip:
                self.optimize_btn.setToolTip(self.tr("platform_tooltip"))

        safe_update(
            "ui_lang_group", QGroupBox, lambda w: w.setTitle(self.tr("ui_language"))
        )
        safe_update("theme_group", QGroupBox, lambda w: w.setTitle(self.tr("theme")))
        safe_update(
            "font_group", QGroupBox, lambda w: w.setTitle(self.tr("font_family"))
        )
        safe_update(
            "help_group", QGroupBox, lambda w: w.setTitle(self.tr("help_support"))
        )

        # Update manual label
        manual_label = getattr(self, "manual_label", None)
        if manual_label:
            manual_label.setText(self.tr("manual_guide"))

        # Update contact label
        if hasattr(self, "contact_label"):
            self.contact_label.setText(
                f"<br><b>{self.tr('contact_support')}</b><br>"
                "<a href='mailto:celsoexpert@gmail.com' style='color: #cfcfcf; text-decoration: none;'>"
                "celsoexpert@gmail.com</a>"
            )

        safe_update("log_group", QGroupBox, lambda w: w.setTitle(self.tr("log")))

        # Update restart button with recycle icon
        safe_update(
            "restart_btn", QPushButton, lambda w: w.setText("🔄 " + self.tr("restart"))
        )

        # Update exit button with door icon
        safe_update(
            "exit_btn", QPushButton, lambda w: w.setText("🚪 " + self.tr("exit"))
        )
        safe_update(
            "developer_label", QLabel, lambda w: w.setText(self.tr("developer"))
        )
        safe_update(
            "copyright_label",
            QLabel,
            lambda w: w.setText(self.tr("developer_footer")),
        )

        self._apply_theme_panels()
        self._update_action_states()

    def is_rtl_language(self) -> bool:
        """Verifica se o idioma atual usa direção RTL."""
        return self.current_ui_lang in {"ar"}

    def apply_layout_direction(self):
        """Aplica direção de layout (LTR/RTL) para toda a UI."""
        direction = (
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )
        app = QApplication.instance()
        if app:
            app.setLayoutDirection(direction)
        self.setLayoutDirection(direction)
        if hasattr(self, "tabs"):
            self.tabs.setLayoutDirection(direction)
        if self.menuBar():
            self.menuBar().setLayoutDirection(direction)
        central = self.centralWidget()
        if central:
            central.setLayoutDirection(direction)

    def _apply_rtl_label(self, label: QLabel):
        """Aplica alinhamento RTL em labels quando necessário."""
        if self.is_rtl_language():
            label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

    def _clean_tab_label(self, label: str) -> str:
        """Remove numeração dos títulos das abas para evitar gaps."""
        if not label:
            return label
        cleaned = re.sub(r"\s\d+\.\s*", " ", label)
        return cleaned.strip()

    def _is_supported_platform(self, text: str) -> bool:
        """Define suporte V1 (apenas Master System)."""
        return text.strip() == "Sega Master System (1985)"

    def _log_info_once(self, message: str, key: str = "info_once") -> None:
        """Loga uma mensagem apenas uma vez para evitar spam."""
        if not hasattr(self, "_info_once_flags"):
            self._info_once_flags = set()
        if key in self._info_once_flags:
            return
        self._info_once_flags.add(key)
        try:
            self.log(message)
        except Exception:
            pass

    # NOTE: retranslate_graphics_lab() has been moved to gui_tabs/graphic_lab.py

    def _get_theme_colors(self):
        theme = ProjectConfig.THEMES.get(
            self.current_theme, ProjectConfig.THEMES["Preto (Black)"]
        )
        return theme

    def _get_theme_border_color(self) -> str:
        theme = self._get_theme_colors()
        return _get_theme_border_color(self.current_theme, theme["window"])

    def _apply_theme_panels(self):
        theme = self._get_theme_colors()
        panel_bg = (
            "#3A3A3A" if self.current_theme == "Cinza (Gray)" else theme["button"]
        )
        panel_border = self._get_theme_border_color()
        text_muted = QColor(theme["text"]).darker(140).name()

        if hasattr(self, "engine_detection_scroll"):
            self.engine_detection_scroll.setStyleSheet(
                f"""
                QScrollArea {{
                    border: 1px solid {panel_border};
                    border-radius: 6px;
                    background-color: {panel_bg};
                }}
                """
            )

        if hasattr(self, "engine_detection_label"):
            self.engine_detection_label.setStyleSheet(
                f"color: {text_muted}; background: {panel_bg}; padding: 10px; border-radius: 5px;"
            )

        if hasattr(self, "graphics_tech_note") and self.graphics_tech_note:
            self.graphics_tech_note.setStyleSheet(
                f"""
                font-size: 12px;
                color: {text_muted};
                background-color: {panel_bg};
                padding: 15px;
                border-radius: 8px;
                border: 1px solid {panel_border};
                """
            )

        if hasattr(self, "realtime_group") and self.realtime_group:
            self.realtime_group.setStyleSheet(
                f"""
                QGroupBox {{
                    font-weight: bold;
                    border: 2px solid {panel_border};
                    border-radius: 8px;
                    margin-top: 10px;
                    padding: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: {text_muted};
                }}
            """
            )

    def _refresh_theme_styles(self):
        """Reaplica estilos locais dependentes do tema."""
        neutral_button_style = self._get_neutral_button_style()
        if hasattr(self, "log_toggle_btn") and self.log_toggle_btn:
            self.log_toggle_btn.setStyleSheet(self._get_unified_button_style())

        for attr_name in [
            "forensic_analysis_btn",
            "select_rom_btn",
            "extract_btn",
            "ascii_probe_btn",
            "load_txt_btn",
            "optimize_btn",
            "sel_file_btn",
            "clear_cache_btn",
            "export_gfx_diag_btn",
            "translate_btn",
            "stop_translation_btn",
            "select_reinsert_rom_btn",
            "select_translated_btn",
            "reinsert_btn",
        ]:
            btn = getattr(self, attr_name, None)
            if isinstance(btn, QAbstractButton):
                btn.setStyleSheet(neutral_button_style)

        if hasattr(self, "eye_btn") and self.eye_btn:
            theme = self._get_theme_colors()
            btn_hover = (
                QColor(theme["button"]).lighter(110).name()
                if self.current_theme != "Preto (Black)"
                else theme["button"]
            )
            eye_btn_style = (
                neutral_button_style.replace("QPushButton", "QToolButton")
                + f"""
                QToolButton {{ padding: 0px; font-size: 11pt; }}
                QToolButton:hover {{ background: {btn_hover}; border-radius: 6px; }}
            """
            )
            self.eye_btn.setStyleSheet(eye_btn_style)

    def _apply_font_to_widgets(self, font: QFont):
        # Aplica fonte para toda a janela e filhos
        self.setFont(font)
        for w in self.findChildren(QWidget):
            w.setFont(font)
        if hasattr(self, "menuBar"):
            self.menuBar().setFont(font)
        if hasattr(self, "eye_btn") and self.eye_btn:
            # Garante fonte com suporte a emoji no botão de visibilidade da API
            self.eye_btn.setFont(QFont("Segoe UI Emoji", 11))

    def change_theme(self, theme_name: str):
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key
        ThemeManager.apply(QApplication.instance(), internal_key)
        self._apply_theme_panels()
        self._refresh_theme_styles()
        self.setup_menu()
        try:
            mb = self.menuBar()
            mb.setVisible(True)
            mb.setNativeMenuBar(False)
        except Exception:
            pass
        try:
            self.repaint()
        except Exception:
            pass
        self.save_config()
        if getattr(self, "debug_mode", False) or os.environ.get("NEUROROM_DEBUG"):
            self.log(f"Tema alterado para: {internal_key}")

    def change_font_family(self, font_name: str):
        self.current_font_family = font_name
        font_family_string = ProjectConfig.FONT_FAMILIES[font_name]
        primary_font = font_family_string.split(",")[0].strip()
        available_fonts = QFontDatabase.families()
        if primary_font not in available_fonts:
            # Tenta normalizar buscando por substring
            matches = [f for f in available_fonts if primary_font.lower() in f.lower()]
            if matches:
                primary_font = matches[0]
            else:
                self.log(
                    f"[WARN] Fonte '{primary_font}' não encontrada. Usando fallback do sistema."
                )
        font = QFont()
        font.setFamily(primary_font)
        font.setPointSize(10)
        app = QApplication.instance()
        app.setFont(font)
        self._apply_font_to_widgets(font)
        # Força repintura para widgets com stylesheet
        ThemeManager.apply(app, self.current_theme)
        self._refresh_theme_styles()
        applied_family = QFontInfo(font).family()
        if applied_family != primary_font:
            self.log(
                f"[INFO] Fonte aplicada: {applied_family} (fallback de {primary_font})"
            )
        self.update()
        self.save_config()

    def _eye_show_key(self):
        """Mostra a chave enquanto o botão está pressionado."""
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.eye_btn.setText("🔒")

    def _eye_hide_key(self):
        """Oculta a chave ao soltar o botão."""
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.eye_btn.setText("👁")

    def validate_file_platform_match(self, detected_engine, selected_platform_text):
        """
        Valida se o arquivo detectado é compatível com a plataforma selecionada.

        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        detected_type = detected_engine.get("type", "UNKNOWN")
        if not detected_type or detected_type == "UNKNOWN":
            # Se não houver detecção confiável, não bloqueia o usuário
            return True, ""

        # Mapa: Nome da plataforma → Tipos/extensões aceitas
        platform_compatibility = {
            "Sega Master System (1985)": {
                "types": ["ROM"],
                "platforms": ["SMS ROM", "Sega Master System"],
                "extensions": [".sms"],
                "engine": "Console",
            },
            "Super Nintendo (SNES)": {
                "types": ["ROM"],
                "platforms": ["SNES ROM"],
                "extensions": [".smc", ".sfc"],
                "engine": "Console",
            },
            "Nintendo Entertainment System (NES)": {
                "types": ["ROM"],
                "platforms": ["NES ROM"],
                "extensions": [".nes"],
                "engine": "Console",
            },
            "Game Boy Advance (GBA)": {
                "types": ["ROM"],
                "platforms": ["Game Boy Advance ROM"],
                "extensions": [".gba"],
                "engine": "Console",
            },
            "Nintendo 64 (N64)": {
                "types": ["ROM"],
                "platforms": ["Nintendo 64 ROM"],
                "extensions": [".z64", ".n64"],
                "engine": "Console",
            },
            "Nintendo DS (NDS)": {
                "types": ["ROM"],
                "platforms": ["Nintendo DS ROM"],
                "extensions": [".nds"],
                "engine": "Console",
            },
            "Game Boy / Game Boy Color": {
                "types": ["ROM"],
                "platforms": ["Game Boy ROM", "Game Boy Color ROM"],
                "extensions": [".gb", ".gbc"],
                "engine": "Console",
            },
            "PC Games (Windows)": {
                "types": ["PC_GAME"],
                "platforms": [
                    "Doom WAD",
                    "PAK Archive",
                    "PC Executable",
                    "Unity Assets",
                    "JSON Data",
                    "RenPy Script",
                ],
                "extensions": [
                    ".exe",
                    ".wad",
                    ".pak",
                    ".dat",
                    ".assets",
                    ".json",
                    ".rpy",
                    ".txt",
                ],
                "engine": None,  # Variável
            },
            "PlayStation 1 (PS1)": {
                "types": ["ROM"],
                "platforms": [
                    "PlayStation/Genesis ROM",
                    "CD-ROM (PS1/PS2/GameCube/etc)",
                ],
                "extensions": [".bin", ".iso"],
                "engine": "Console",
            },
        }

        # Plataformas em desenvolvimento (bloquear completamente)
        platforms_in_development = [
            "PlayStation 2 (PS2)",
            "PlayStation 3 (PS3)",
            "Sega Mega Drive",
            "Sega Master System",
            "Sega Dreamcast",
            "Xbox",
            "Xbox 360",
        ]

        # Verificar se plataforma está em desenvolvimento
        if selected_platform_text in platforms_in_development:
            error_msg = self.tr("platform_in_development_message").format(
                selected=selected_platform_text
            )
            return False, error_msg

        # Obter compatibilidade da plataforma selecionada
        compatibility = platform_compatibility.get(selected_platform_text)

        if not compatibility:
            # Plataforma desconhecida ou não mapeada
            error_msg = self.tr("platform_not_recognized_message").format(
                selected=selected_platform_text
            )
            return False, error_msg

        # Extrair informações da detecção
        detected_platform = detected_engine.get("platform", "Unknown")
        detected_extension = detected_engine.get("extension", "")

        # Verificar compatibilidade por tipo
        if detected_type not in compatibility["types"]:
            # Tipo incompatível (ROM vs PC_GAME)
            if detected_type == "PC_GAME" and "ROM" in compatibility["types"]:
                error_msg = self.tr("incompatible_file_pc_message").format(
                    selected=selected_platform_text,
                    detected=detected_platform,
                )
                return False, error_msg
            elif detected_type == "ROM" and "PC_GAME" in compatibility["types"]:
                error_msg = self.tr("incompatible_file_rom_message").format(
                    selected=selected_platform_text,
                    detected=detected_platform,
                )
                return False, error_msg

        # Verificar compatibilidade por extensão (mais específico)
        if detected_extension and detected_extension not in compatibility["extensions"]:
            # Extensão incompatível com a plataforma
            expected_ext = ", ".join(compatibility["extensions"])
            error_msg = self.tr("incompatible_extension_message").format(
                selected=selected_platform_text,
                expected=expected_ext,
                detected=detected_platform,
                ext=detected_extension,
            )
            return False, error_msg

        # Se chegou aqui, arquivo é compatível!
        return True, ""

    def select_rom(self):
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if hasattr(self, "last_rom_dir") and self.last_rom_dir:
            initial_dir = self.last_rom_dir
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("dialog_select_rom_title"),
            initial_dir,
            self.tr("dialog_select_rom_filters"),
        )
        if file_path:
            detection = None
            # Validação automática de compatibilidade
            try:
                detection = detect_game_engine(file_path)
                is_valid, error_msg = self.validate_file_platform_match(
                    detection, self.platform_combo.currentText()
                )
                if not is_valid:
                    QMessageBox.warning(
                        self, self.tr("dialog_title_error"), error_msg
                    )
                    return
            except Exception:
                pass

            self.last_rom_dir = os.path.dirname(file_path)
            self.save_config()
            self.original_rom_path = file_path
            rom_size = os.path.getsize(file_path)
            crc32_full = _crc32_file(file_path)
            self.current_rom_crc32 = crc32_full
            self.current_rom_size = rom_size
            if detection:
                self.detected_engine = detection
            candidate_output = os.path.join(os.path.dirname(file_path), crc32_full)
            self.current_output_dir = (
                candidate_output if os.path.isdir(candidate_output) else None
            )
            if self.current_output_dir:
                # Auto-limpeza: esconde arquivos auxiliares de extrações anteriores
                self._stash_auxiliary_outputs(self.current_output_dir, crc32_full)
                self._set_text_dir_from_output_dir(self.current_output_dir)
                self.log(
                    self.tr("hint_files_location").format(
                        folder=self.current_output_dir
                    )
                )
            self.rom_path_label.setText(self._rom_identity_text(crc32_full, rom_size))
            self.rom_path_label.setStyleSheet("color: #cfcfcf;")  # Neutro

            # HABILITA o botão de análise forense
            self.forensic_analysis_btn.setEnabled(True)
            if hasattr(self, "ascii_probe_btn"):
                self.ascii_probe_btn.setEnabled(True)

            self.log(f"[OK] ROM selecionada | {self._rom_identity_text(crc32_full, rom_size)}")
            self._sync_graphics_lab_rom(file_path)
            self._maybe_activate_graphics_from_detection(detection)

            # Atualiza o label da aba de reinserção
            self.reinsert_rom_label.setText(self.tr("status_rom_selected"))
            self.reinsert_rom_label.setToolTip(
                self._rom_identity_text(crc32_full, rom_size)
            )
            self.reinsert_rom_label.setStyleSheet("color: #cfcfcf;")

            # Atualiza o campo de saída da ROM traduzida (usa nome do arquivo)
            ext = Path(file_path).suffix
            out_ext = ext if ext else ".rom"
            self.output_rom_edit.setText(f"{crc32_full}_TRANSLATED{out_ext}")

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

            arquivo_encontrado = _find_latest_in_texts(
                {
                    f"{rom_filename}_clean_blocks.txt",
                    f"{rom_filename}_extracted.txt",
                    f"{rom_filename}_CLEAN_EXTRACTED.txt",
                    f"{rom_filename}_V98_FORENSIC.txt",
                    f"{rom_filename}_V9_EXTRACTED.txt",
                    f"{rom_filename}_extracted_texts.txt",
                }
            )

            if arquivo_encontrado:
                self.extracted_file = arquivo_encontrado
                # se for clean_blocks, salva também como last_clean_blocks
                if arquivo_encontrado.endswith("_clean_blocks.txt"):
                    self.last_clean_blocks = arquivo_encontrado

                self.trans_file_label.setText(self._rom_identity_text())
                self.trans_file_label.setStyleSheet("color: #cfcfcf;")
                self.log(f"📄 Arquivo extraído detectado | {self._rom_identity_text()}")

                # [OK] Busca automática de arquivo otimizado (mais recente)
                opt = None
                if os.path.isdir(texts_dir):
                    opt_candidates = []
                    for root, _, files in os.walk(texts_dir):
                        for fn in files:
                            if fn.startswith(rom_filename) and (
                                "OPTIMIZED" in fn.upper()
                            ):
                                opt_candidates.append(os.path.join(root, fn))
                    if opt_candidates:
                        opt_candidates.sort(
                            key=lambda p: os.path.getmtime(p), reverse=True
                        )
                        opt = opt_candidates[0]

                if opt and os.path.exists(opt):
                    self.optimized_file = opt
                    self.log(f"📄 Arquivo otimizado detectado | {self._rom_identity_text()}")
            elif self.extracted_file and os.path.exists(self.extracted_file):
                self.trans_file_label.setText(self._rom_identity_text())
                self.trans_file_label.setStyleSheet("color: #cfcfcf;")
            self._update_action_states()
        else:
            self.rom_path_label.setText(self.tr("no_rom"))
            self.rom_path_label.setStyleSheet("color: #b0b0b0;")  # Neutro

            # DESABILITA o botão de análise forense
            self.forensic_analysis_btn.setEnabled(False)
            self._update_action_states()

    def executar_varredura_inteligente(self, path_obj):
        """Nova versão: Separa automaticamente Textos e Gráficos."""
        diretorio = path_obj.parent
        self.log("Minerando arquivos...")

        # Extensões para as duas rotas
        ext_texto = (".json", ".txt", ".xml", ".wad", ".msg", ".bin")
        ext_grafico = (".png", ".dds", ".tga", ".bmp", ".jpg")

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
        if not TESSERACT_AVAILABLE:
            self.log("OCR indisponível: instale pytesseract e pillow.")
            return ""

        try:
            # Abre a imagem selecionada
            img = Image.open(caminho_da_imagem)

            # Converte imagem em texto usando o motor OCR
            texto_detectado = pytesseract.image_to_string(img, lang="eng").strip()

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
                cor = "#b0b0b0"
            elif tipo == "PC_GAME":
                emoji = "🟦"
                texto_tipo = self.tr("engine_pc_game")
                cor = "#b0b0b0"
            else:
                emoji = "🟧"
                texto_tipo = self.tr("engine_unknown")
                cor = "#b0b0b0"

            # Montar mensagem HTML
            mensagem = f"{emoji} <b>{self.tr('engine_detected')}</b>: {texto_tipo}<br>"
            mensagem += f"<b>{self.tr('engine_platform')}</b>: {plataforma}<br>"
            mensagem += f"<b>Engine:</b> {engine}<br>"

            if observacoes:
                mensagem += f"<br><small>{observacoes}</small>"

            if sugestao_conversor:
                mensagem += f"<br><br><b style='color:#4AC45F'>🔄 Conversor sugerido:</b> <code>{sugestao_conversor}</code>"

            # Atualizar interface
            panel_bg = self._get_theme_colors()["button"]
            self.engine_detection_label.setText(mensagem)
            self.engine_detection_label.setStyleSheet(
                f"color:#e0e0e0;background:{panel_bg};padding:10px;border-radius:5px;border-left:3px solid {cor};border-right:3px solid {cor};"
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
            if file_ext in [".exe", ".dat"]:
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
                engine_type = "PC_GAME"

            elif file_ext == ".wad":
                engine = "id Tech 1 (Doom Engine)"
                platform = "PC (DOS/Windows)"
                notes = "Classic FPS Engine (1993-1998)"
                type_emoji = "💻"
                type_text = "PC Game"
                color = "#2196F3"
                engine_type = "PC_GAME"

            elif file_ext in [".smc", ".sfc"]:
                engine = "SNES Cartridge"
                platform = "Super Nintendo (16-bit)"
                notes = "Console clássico (1990-1996)"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = "ROM"

            elif file_ext == ".nes":
                engine = "NES iNES Format"
                platform = "Nintendo Entertainment System"
                notes = "Console 8-bit (1983-1994)"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = "ROM"

            elif file_ext in [".gba", ".gb", ".gbc"]:
                console_names = {
                    ".gba": "Game Boy Advance",
                    ".gb": "Game Boy",
                    ".gbc": "Game Boy Color",
                }
                platform = console_names.get(file_ext, "Nintendo Handheld")
                engine = "Nintendo Handheld"
                notes = "Portátil Nintendo"
                type_emoji = "🎮"
                type_text = "Console ROM"
                color = "#4CAF50"
                engine_type = "ROM"

            elif file_ext in [".iso", ".img", ".bin"]:
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
                engine_type = "ROM"

            else:
                engine = f"Binary File ({file_ext.upper()[1:]})"
                platform = "Generic"
                notes = f"Tamanho: {file_size_mb:.1f} MB"
                type_emoji = "📄"
                type_text = "Generic File"
                color = "#FF9800"
                engine_type = "UNKNOWN"

            # Armazena detecção
            self.detected_engine = {
                "type": engine_type,
                "platform": platform,
                "engine": engine,
                "notes": notes,
            }

            # Atualiza UI
            detection_text = f"{type_emoji} <b>Detectado:</b> {type_text}<br>"
            detection_text += f"<b>Plataforma:</b> {platform}<br>"
            detection_text += f"<b>Engine:</b> {engine}"
            if notes:
                detection_text += f"<br><small>{notes}</small>"

            self.engine_detection_label.setText(detection_text)
            color = "#b0b0b0"
            panel_bg = self._get_theme_colors()["button"]
            self.engine_detection_label.setStyleSheet(
                f"color:{color};background:{panel_bg};padding:10px;border-radius:5px;border-left:3px solid {color};border-right:3px solid {color};"
            )
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
            if (
                self.engine_detection_thread
                and self.engine_detection_thread.isRunning()
            ):
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
            self.engine_detection_thread.progress_signal.connect(
                self.on_engine_detection_progress
            )
            self.engine_detection_thread.detection_complete.connect(
                self.on_engine_detection_complete
            )

            # Exibe status inicial
            self.engine_detection_label.setText(self.tr("forensic_starting"))
            panel_bg = self._get_theme_colors()["button"]
            self.engine_detection_label.setStyleSheet(
                f"color:#b0b0b0;background:{panel_bg};padding:10px;border-radius:5px;"
            )
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
            engine_type = detection_result.get("type", "UNKNOWN")
            platform = detection_result.get("platform", "Unknown")
            engine = detection_result.get("engine", "Unknown")
            notes = detection_result.get("notes", "")

            # NOVOS CAMPOS TIER 1
            year_estimate = detection_result.get("year_estimate", None)
            compression = detection_result.get("compression", "N/A")
            confidence = detection_result.get("confidence", "N/A")
            entropy = detection_result.get("entropy", 0.0)
            warnings = detection_result.get("warnings", [])
            recommendations = detection_result.get("recommendations", [])

            # NOVOS CAMPOS TIER 1 ADVANCED (Contextual Fingerprinting)
            contextual_patterns = detection_result.get("contextual_patterns", [])
            architecture_inference = detection_result.get(
                "architecture_inference", None
            )

            # NOVOS CAMPOS DEEP FINGERPRINTING (RAIO-X FORENSE)
            deep_analysis = detection_result.get("deep_analysis", None)

            # ================================================================
            # OVERRIDE VIA CRC32/ROM_SIZE (BASE LOCAL, SEM NOMES)
            # ================================================================
            crc_entry = self._get_crc_forensic_entry()
            if crc_entry:
                if crc_entry.get("engine"):
                    engine = crc_entry.get("engine")
                if crc_entry.get("year"):
                    year_estimate = crc_entry.get("year")

            # EXTRAÇÃO ANTECIPADA DO ANO DO JOGO (PRIORIDADE SOBRE INSTALADOR)
            game_year_from_deep = None
            if deep_analysis and deep_analysis.get("game_year"):
                game_year_from_deep = deep_analysis.get("game_year")
                # SOBRESCREVER year_estimate com ano do jogo (prioridade)
                year_estimate = game_year_from_deep

            # ================================================================
            # ESCOLHA DE EMOJI E COR POR TIPO
            # ================================================================
            type_emoji_map = {
                "ROM": ("🎮", "Console ROM", "#4CAF50"),
                "PC_GAME": ("💻", "PC Game", "#2196F3"),
                "PC_GENERIC": ("💻", "PC Executável", "#64B5F6"),
                "INSTALLER": ("[WARN]", "INSTALADOR", "#FF9800"),
                "ARCHIVE": ("📦", "Arquivo Compactado", "#9C27B0"),
                "ERROR": ("[ERROR]", "Erro", "#FF5722"),
                "UNKNOWN": ("❓", "Desconhecido", "#757575"),
                "GENERIC": ("📄", "Arquivo Genérico", "#FF9800"),
            }

            type_emoji, type_text, color = type_emoji_map.get(
                engine_type, ("📄", "Arquivo Genérico", "#FF9800")
            )
            color = "#b0b0b0"

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
            for det in detection_result.get("detections", []):
                if det.get("category") == "SNES_HEADER":
                    snes_header_data = det.get("snes_data")
                    break

            if snes_header_data:
                # Neutralidade V1: exibir apenas CRC32 e ROM_SIZE, não Title/Region/MapType/CartType
                detection_text += "<br><b>🎮 INFORMAÇÕES DA ROM SNES:</b><br>"

                rom_size = snes_header_data.get("rom_size_kb", 0)
                if rom_size > 0:
                    rom_size_mb = rom_size / 1024
                    detection_text += f"<b>📦 Tamanho da ROM:</b> {rom_size} KB ({rom_size_mb:.2f} MB)<br>"

            # Ano Estimado
            if year_estimate:
                detection_text += f"<b>📅 Ano Estimado:</b> {year_estimate}<br>"
            else:
                detection_text += "<b>📅 Ano Estimado:</b> <i>Não detectado</i><br>"

            # Compressão + Entropia
            detection_text += f"<b>🔧 Compressão:</b> {compression}<br>"

            # Confiança
            detection_text += f"<b>🎯 Confiança:</b> {confidence}<br>"

            # ================================================================
            # DEEP FINGERPRINTING (RAIO-X) - Exibição de features do jogo
            # ================================================================
            if deep_analysis and deep_analysis.get("patterns_found"):
                pattern_count = len(deep_analysis["patterns_found"])
                game_year_from_deep = deep_analysis.get("game_year")
                architecture_from_deep = deep_analysis.get("architecture_hints", [])
                features_from_deep = deep_analysis.get("feature_icons", [])

                detection_text += f"<br><b>🔬 RAIO-X DO INSTALADOR:</b> {pattern_count} padrões do jogo detectados<br>"

                # Mostrar arquitetura inferida do jogo
                if architecture_from_deep:
                    arch_name = architecture_from_deep[0]
                    detection_text += f"<b>🏗️ Jogo Detectado:</b> {arch_name}<br>"

                # Mostrar ano do jogo (não do instalador) - PRIORIDADE
                if game_year_from_deep:
                    detection_text += (
                        f"<b>📅 Ano do Jogo:</b> {game_year_from_deep}<br>"
                    )

                # Mostrar features detectadas (VERTICAL - um por linha)
                if features_from_deep:
                    detection_text += "<br><b>🎮 Features Encontradas no Jogo:</b><br>"
                    for feature in features_from_deep[:10]:  # Máximo 10 features
                        detection_text += f"<small>• {feature}</small><br>"

            # ================================================================
            # CONTEXTUAL FINGERPRINTING (TIER 1 ADVANCED)
            # ================================================================
            if architecture_inference:
                arch_name = architecture_inference.get("architecture", "N/A")
                game_type = architecture_inference.get("game_type", "N/A")
                year_range = architecture_inference.get("year_range", "N/A")
                based_on = architecture_inference.get("based_on", "N/A")

                detection_text += f"<br><b>🏗️ Arquitetura Detectada:</b> {arch_name}<br>"
                detection_text += f"<b>[STATS] Tipo de Jogo:</b> {game_type}<br>"
                detection_text += f"<b>📅 Período:</b> {year_range}<br>"
                detection_text += f"<small><i>Baseado em: {based_on}</i></small><br>"

            # Padrões Contextuais Encontrados
            if contextual_patterns:
                detection_text += f"<br><b>🎯 Padrões Contextuais:</b> {len(contextual_patterns)} encontrados<br>"
                for pattern in contextual_patterns[:3]:  # Mostrar até 3 padrões
                    pattern_desc = pattern.get("description", "N/A")
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
            panel_bg = self._get_theme_colors()["button"]
            self.engine_detection_label.setStyleSheet(
                f"""
                color: {color};
                background: {panel_bg};
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid {color};
                border-right: 4px solid {color};
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
            platform_code = detection_result.get("platform_code")
            if platform_code and platform_code not in ["INSTALLER", "ARCHIVE"]:
                self.sync_platform_combobox(platform_code)
            else:
                # Para INSTALADORES e ARCHIVES, ocultar banner laranja de "em desenvolvimento"
                if hasattr(self, "console_warning_widget"):
                    self.console_warning_widget.setVisible(False)
                # (Linhas acima...)
                if hasattr(self, "console_warning_widget"):
                    self.console_warning_widget.setVisible(False)  #

            # ============================================================
            # FINALIZAÇÃO DA ANÁLISE FORENSE (MODO SEGURO)
            # ============================================================
            if hasattr(self, "forensic_progress"):
                self.forensic_progress.setVisible(False)

            if hasattr(self, "forensic_analysis_btn"):
                self.forensic_analysis_btn.setEnabled(True)

            # Limpa a referência da thread se ela existir
            if hasattr(self, "engine_detection_thread"):
                self.engine_detection_thread = None

        except Exception as e:
            error_msg = f"[WARN] Erro ao processar detecção: {_sanitize_error(e)}"
            self.log(error_msg)

            # Mostra erro genérico
            self.engine_detection_label.setText(
                f"[ERROR] <b>Erro na Análise Forense</b><br>"
                f"<small>{error_msg}</small>"
            )
            panel_bg = self._get_theme_colors()["button"]
            self.engine_detection_label.setStyleSheet(
                f"color:#cfcfcf;background:{panel_bg};padding:10px;border-radius:5px;"
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
                "SNES": "Super Nintendo (SNES)",
                "NES": "Nintendo (NES)",
                "PS1": "PlayStation 1 (PS1)",
                "GENESIS": "Sega Genesis / Mega Drive",
                "GB": "Game Boy (GB/GBC)",
                "GBA": "Game Boy Advance (GBA)",
                "PC": "PC Games (Windows)",  # Auto-seleciona PC Games
            }

            target_platform = platform_mapping.get(platform_code)

            if not target_platform:
                return  # Não faz nada para PC ou códigos desconhecidos

            # Procura pelo item no ComboBox
            for i in range(self.platform_combo.count()):
                item_text = self.platform_combo.itemText(i)

                # Verifica se encontrou a plataforma correta
                if target_platform in item_text or item_text.startswith(
                    target_platform
                ):
                    # Verifica se o item está habilitado
                    item = self.platform_combo.model().item(i)
                    if item and item.isEnabled():
                        self.platform_combo.setCurrentIndex(i)
                        self.log(f"[OK] ComboBox sincronizado: {item_text}")
                        return

            self.log(
                f"[WARN] Plataforma '{target_platform}' não encontrada no ComboBox"
            )

        except Exception as e:
            self.log(f"[WARN] Erro ao sincronizar ComboBox: {_sanitize_error(e)}")

    def preencher_lista_laboratorio(self, lista_caminhos):
        """Envia imagens para o GraphicLabTab (CORRIGIDO - sem erro de widget)."""
        try:
            if self.graphics_lab_tab:
                # Muda para aba do Laboratório Gráfico
                if hasattr(self, "tabs"):
                    idx = self.tabs.indexOf(self.graphics_lab_tab)
                    if idx >= 0:
                        self.tabs.setCurrentIndex(idx)

                self.log(f"[OK] {len(lista_caminhos)} gráficos detectados")
                self.log(
                    "💡 Use o botão '🎨 CARREGAR TEXTURA' no Laboratório Gráfico para visualizar"
                )

                # Salva paths temporariamente para o usuário carregar manualmente
                temp_file = os.path.join(
                    os.path.dirname(__file__), "..", ".pending_graphics.json"
                )
                import json

                with open(temp_file, "w") as f:
                    json.dump(lista_caminhos, f)

            else:
                self.log("[WARN] GraphicLabTab não disponível")
        except Exception as e:
            self.log(f"[ERROR] Erro ao processar gráficos: {_sanitize_error(e)}")

    def _sync_graphics_lab_rom(self, rom_path: str):
        """Sincroniza a ROM atual com o Laboratório Gráfico."""
        if not rom_path:
            return
        if self.graphics_lab_tab and hasattr(self.graphics_lab_tab, "set_rom_path"):
            try:
                self.graphics_lab_tab.set_rom_path(rom_path)
            except Exception:
                pass

    def run_auto_graphics_pipeline(self):
        """Executa pipeline gráfico automático (se habilitado)."""
        if not getattr(self, "auto_graphics_pipeline", False):
            return
        if not self.graphics_lab_tab:
            return
        try:
            self._sync_graphics_lab_rom(self.original_rom_path)
            api_key = self.api_key_edit.text().strip() if hasattr(self, "api_key_edit") else ""
            target_lang = self.target_lang_combo.currentText() if hasattr(self, "target_lang_combo") else "Portuguese (Brazil)"
            result = self.graphics_lab_tab.auto_graphics_pipeline(
                api_key=api_key, target_language=target_lang
            )
            if isinstance(result, dict):
                self.gfx_needs_review = int(result.get("needs_review_gfx", 0))
                if self.gfx_needs_review > 0 and hasattr(self, "export_gfx_diag_btn"):
                    self.export_gfx_diag_btn.setVisible(True)
                    self.export_gfx_diag_btn.setText(
                        f"Exportar diagnóstico gráfico ({self.gfx_needs_review})"
                    )
        except Exception as e:
            self.log(f"[WARN] Pipeline gráfico automático falhou: {_sanitize_error(e)}")

    def export_gfx_diagnostic(self):
        """Exporta diagnóstico gráfico quando houver needs_review_gfx."""
        if not self.graphics_lab_tab:
            self.log("[WARN] Laboratório Gráfico não disponível.")
            return
        try:
            out_dir = self.graphics_lab_tab.export_gfx_debug_pack()
            if out_dir:
                self.log(f"[OK] Diagnóstico gráfico exportado: {out_dir}")
                QMessageBox.information(
                    self,
                    self.tr("dialog_title_info"),
                    f"Diagnóstico gráfico exportado em:\n{out_dir}",
                )
        except Exception as e:
            self.log(f"[WARN] Falha ao exportar diagnóstico gráfico: {_sanitize_error(e)}")

    def _activate_graphics_tab(self, reason: str = ""):
        """Ativa automaticamente a aba do Laboratório Gráfico."""
        if not getattr(self, "developer_mode", False):
            return
        if not self.graphics_lab_tab or not hasattr(self, "tabs"):
            return
        idx = self.tabs.indexOf(self.graphics_lab_tab)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
        if reason:
            self.log(f"🎨 Laboratório Gráfico ativado automaticamente ({reason}).")
        if hasattr(self.graphics_lab_tab, "auto_scan_and_ocr"):
            QTimer.singleShot(100, self.graphics_lab_tab.auto_scan_and_ocr)

    def _maybe_activate_graphics_from_detection(self, detection: dict | None):
        """Ativa o Laboratório Gráfico quando o engine indica uso de tiles/gráficos."""
        if not detection:
            return
        tipo = str(detection.get("type", "")).upper()
        engine = str(detection.get("engine", "")).upper()
        notes = str(detection.get("notes", "")).upper()
        if tipo != "ROM":
            return
        if ("TILE" in engine) or ("TILE" in notes) or ("SPRITE" in engine):
            self._activate_graphics_tab("engine gráfico detectado")

    def select_translation_input_file(self):
        initial_dir = str(ProjectConfig.ROMS_DIR)
        # Prioriza pasta CRC32 (NÃO _interno — _interno é só diagnóstico)
        output_dir = self._get_output_dir_for_current_rom()
        if output_dir and os.path.isdir(output_dir):
            initial_dir = output_dir
        elif hasattr(self, "last_text_dir") and self.last_text_dir:
            initial_dir = self.last_text_dir
        elif self.original_rom_path and os.path.exists(
            os.path.dirname(self.original_rom_path)
        ):
            initial_dir = os.path.dirname(self.original_rom_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("select_file"),
            initial_dir,
            self.tr("dialog_filter_text_files"),
        )

        if file_path:
            # Bloqueia arquivos internos/diagnóstico automaticamente
            fname_lower = os.path.basename(file_path).lower()
            path_normalized = file_path.replace("\\", "/").lower()
            if (
                "_interno" in path_normalized
                or "_all_text" in fname_lower
                or "_suspect" in fname_lower
            ):
                QMessageBox.warning(
                    self,
                    self.tr("dialog_title_warning"),
                    "Arquivo interno/diagnóstico bloqueado.\n"
                    "Use {CRC32}_pure_text.jsonl como arquivo para traduzir.",
                )
                return

            # Alerta para arquivos muito grandes (possível diagnóstico)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as _f:
                    _line_count = sum(1 for _ in _f)
                if _line_count > 2000:
                    resp = QMessageBox.question(
                        self,
                        self.tr("dialog_title_warning"),
                        f"Arquivo tem {_line_count} linhas (> 2000).\n"
                        "Pode ser um arquivo de diagnóstico (Cobertura Total).\n\n"
                        "Deseja usar mesmo assim?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if resp != QMessageBox.StandardButton.Yes:
                        return
            except Exception:
                pass

            self._set_output_dir_from_file(file_path)
            self.last_text_dir = os.path.dirname(file_path)
            self.save_config()
            self.optimized_file = file_path
            txt_size = os.path.getsize(file_path)
            self.trans_file_label.setText(f"TXT ({txt_size} bytes)")
            self.trans_file_label.setStyleSheet("color: #cfcfcf; font-weight: bold;")
            self.log(f"Arquivo carregado para tradução | FILE_SIZE={txt_size}")
            self._update_action_states()

            # Inferência de ROM desabilitada para neutralidade
            rom_directory = os.path.dirname(file_path)

    def load_extracted_txt_directly(self):
        """
        Carrega arquivo TXT já extraído e infere automaticamente a ROM original.
        Facilita quando usuário já tem o arquivo _CLEAN_EXTRACTED.txt pronto.
        """
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if hasattr(self, "last_text_dir") and self.last_text_dir:
            initial_dir = self.last_text_dir
        elif self.original_rom_path and os.path.exists(
            os.path.dirname(self.original_rom_path)
        ):
            initial_dir = os.path.dirname(self.original_rom_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("dialog_select_extracted_title"),
            initial_dir,
            self.tr("dialog_select_extracted_filters"),
        )

        if not file_path:
            return

        # Salva arquivo extraído
        self._set_output_dir_from_file(file_path)
        self.last_text_dir = os.path.dirname(file_path)
        self.save_config()
        self.extracted_file = file_path
        txt_size = os.path.getsize(file_path)
        self.trans_file_label.setText(f"TXT ({txt_size} bytes)")
        self.trans_file_label.setStyleSheet("color: #cfcfcf; font-weight: bold;")
        self.log(f"[OK] Arquivo TXT carregado | FILE_SIZE={txt_size}")
        self._update_action_states()

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
            filtros = self.tr("dialog_filter_rom_default")
            self.log("🔍 Filtro genérico de reinserção")

        initial_dir = str(ProjectConfig.ROMS_DIR)
        if hasattr(self, "last_rom_dir") and self.last_rom_dir:
            initial_dir = self.last_rom_dir
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), initial_dir, filtros
        )
        if file_path:
            # Validação automática de compatibilidade
            try:
                detection = detect_game_engine(file_path)
                is_valid, error_msg = self.validate_file_platform_match(
                    detection, self.platform_combo.currentText()
                )
                if not is_valid:
                    QMessageBox.warning(
                        self, self.tr("dialog_title_error"), error_msg
                    )
                    return
            except Exception:
                pass

            self.last_rom_dir = os.path.dirname(file_path)
            self.save_config()
            self.original_rom_path = file_path
            rom_size = os.path.getsize(file_path)
            crc32_full = _crc32_file(file_path)
            self.current_rom_crc32 = crc32_full
            self.current_rom_size = rom_size
            candidate_output = os.path.join(os.path.dirname(file_path), crc32_full)
            self.current_output_dir = (
                candidate_output if os.path.isdir(candidate_output) else None
            )
            if self.current_output_dir:
                # Auto-limpeza: esconde arquivos auxiliares de extrações anteriores
                self._stash_auxiliary_outputs(self.current_output_dir, crc32_full)
                self._set_text_dir_from_output_dir(self.current_output_dir)
                self.log(
                    self.tr("hint_files_location").format(
                        folder=self.current_output_dir
                    )
                )
            self.reinsert_rom_label.setText(self.tr("status_rom_selected"))
            self.reinsert_rom_label.setToolTip(self._rom_identity_text(crc32_full, rom_size))
            self.reinsert_rom_label.setStyleSheet("color:#cfcfcf;font-weight:bold;")
            self.rom_path_label.setText(self._rom_identity_text(crc32_full, rom_size))
            self.rom_path_label.setStyleSheet("color:#cfcfcf;font-weight:bold;")

            # Habilitar botão de Análise Forense (Raio-X)
            self.forensic_analysis_btn.setEnabled(True)

            # ================================================================
            # ATUALIZAR PLACEHOLDER DO OUTPUT BASEADO NA PLATAFORMA
            # ================================================================
            file_ext = os.path.splitext(file_path)[1].lower()
            out_ext = file_ext if file_ext else ".rom"
            self.output_rom_edit.setText(f"{crc32_full}_TRANSLATED{out_ext}")
            self._update_action_states()

    def select_translated_file(self):
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if hasattr(self, "last_text_dir") and self.last_text_dir:
            initial_dir = self.last_text_dir
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("select_file"),
            initial_dir,
            "JSONL traduzido (*.jsonl);;Todos os arquivos (*.*)",
        )
        if not file_path:
            return

        # Se o usuário selecionou um diretório acidentalmente (ou arquivo não-.jsonl),
        # tenta localizar automaticamente o JSONL traduzido dentro da pasta.
        resolved = self._resolve_translated_jsonl(file_path)
        if resolved:
            file_path = resolved
        elif not file_path.lower().endswith(".jsonl"):
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                "Selecione um arquivo .jsonl traduzido.\n"
                "Arquivos .txt não contêm metadados de offset necessários para reinserção.",
            )
            return

        self._set_output_dir_from_file(file_path)
        self.last_text_dir = os.path.dirname(file_path)
        self.save_config()
        self.translated_file = file_path
        self.translated_file_label.setText(self._rom_identity_text())
        self.translated_file_label.setStyleSheet("color:#cfcfcf;font-weight:bold;")
        self.log(f"Arquivo traduzido selecionado: {os.path.basename(file_path)}")
        self._update_action_states()

    def _resolve_translated_jsonl(self, path: str):
        """Se *path* for pasta (ou .txt), procura JSONL traduzido automaticamente.

        Busca por ``{CRC32}_translated_fixed.jsonl`` ou
        ``{CRC32}_translated.jsonl`` no root e em ``_interno/``.
        Retorna o caminho resolvido ou None.
        """
        search_dir = path if os.path.isdir(path) else os.path.dirname(path)
        crc = getattr(self, "current_rom_crc32", None) or ""
        candidates = []
        for d in (search_dir, os.path.join(search_dir, "_interno")):
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                low = fn.lower()
                if not low.endswith(".jsonl"):
                    continue
                # Prioriza translated_fixed, depois translated (qualquer CRC)
                if crc and fn.startswith(crc):
                    if "translated_fixed" in low:
                        return os.path.join(d, fn)
                    if "translated" in low:
                        candidates.append(os.path.join(d, fn))
                elif "translated_fixed" in low:
                    candidates.append(os.path.join(d, fn))
                elif "translated" in low:
                    candidates.append(os.path.join(d, fn))
        return candidates[0] if candidates else None

    def reinsert(self):
        output_name = self.output_rom_edit.text().strip()
        if not self.original_rom_path or not os.path.exists(self.original_rom_path):
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_select_original_rom"),
            )
            return
        if not self.translated_file or not os.path.exists(self.translated_file):
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_translated_file_missing"),
            )
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
            crc32_out = self.current_rom_crc32 or _crc32_file(rom_path)
            output_rom_path = os.path.join(
                safe_output_directory, f"{crc32_out}_TRANSLATED{rom_ext or '.rom'}"
            )

        self.log("📁 Pasta de saída segura definida.")

        # Backup automático da ROM original
        backup_path = self._create_rom_backup(rom_path, safe_output_directory)
        if backup_path:
            self.log(self.tr("log_backup_created"))
        else:
            self.log(self.tr("log_backup_failed"))

        # SUPORTE EXPANDIDO: PC Games + ROMs de Console + Sega
        valid_extensions = (
            ".smc",
            ".sfc",
            ".bin",
            ".nes",
            ".z64",
            ".n64",
            ".gba",
            ".gb",
            ".gbc",
            ".nds",
            ".iso",
            ".exe",
            ".dll",
            ".dat",
            ".sms",
            ".md",
            ".gen",
            ".smd",
        )
        if output_name and not output_name.lower().endswith(valid_extensions):
            QMessageBox.warning(
                self,
                self.tr("dialog_title_error"),
                self.tr("error_invalid_extension").format(
                    exts=", ".join(valid_extensions)
                ),
            )
            return

        # Neutralidade V1: não expor nomes de arquivo em logs
        self.log("Starting reinsertion process...")
        self.reinsertion_status_label.setText(
            self.tr("status_reinsertion_preparing")
        )
        self.reinsertion_progress_bar.setValue(0)
        self.reinsert_btn.setEnabled(False)

        force_blocked = bool(
            getattr(self, "force_blocked_checkbox", None)
            and self.force_blocked_checkbox.isChecked()
        )
        self._last_output_rom = output_rom_path
        self.reinsert_thread = ReinsertionWorker(
            rom_path, translated_path, output_rom_path, force_blocked=force_blocked
        )
        self.reinsert_thread.progress_signal.connect(
            self.reinsertion_progress_bar.setValue
        )
        self.reinsert_thread.status_signal.connect(
            lambda text: self._set_status_label(self.reinsertion_status_label, text)
        )
        self.reinsert_thread.log_signal.connect(self.log)
        self.reinsert_thread.finished_signal.connect(self.on_reinsertion_finished)
        self.reinsert_thread.error_signal.connect(self.on_reinsertion_error)
        self.reinsert_thread.start()

    def on_reinsertion_finished(self):
        self.reinsertion_progress_bar.setValue(100)
        self.reinsert_btn.setEnabled(True)
        QMessageBox.information(
            self,
            self.tr("congratulations_title"),
            self.tr("reinsertion_completed_next_message"),
        )
        self.log(self.tr("next_step_test"))
        # Abre Explorer selecionando a ROM patcheada
        patched = getattr(self, "_last_output_rom", "")
        if patched:
            self._explorer_select(patched, os.path.dirname(patched))

    def on_reinsertion_error(self, error_msg):
        self.reinsertion_status_label.setText(self.tr("status_error"))
        self.reinsert_btn.setEnabled(True)
        self.log(f"[ERROR] Erro fatal na reinserção: {error_msg}")
        QMessageBox.critical(
            self,
            self.tr("dialog_title_error"),
            self.tr("error_reinsertion_failed").format(error=error_msg),
        )

    def extract_texts(self):
        """Função do Botão Verde: Extrai os textos da ROM original."""
        if not hasattr(self, "original_rom_path") or not self.original_rom_path:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_select_rom_first"),
            )
            return
        if self.max_extraction_mode:
            self.log(self.tr("max_extraction_active_log"))
        else:
            self.log(self.tr("max_extraction_inactive_log"))

        self.log(
            "[START] Iniciando extração (identificação por CRC32/ROM_SIZE no report)"
        )
        self.extract_progress_bar.setValue(0)

        # Aqui o sistema chama o motor de extração que já tínhamos
        try:
            # Se for SNES, usa a lógica de ponteiros, senão usa Scan Universal
            self.start_extraction_process()
        except Exception as e:
            self.log(f"[ERROR] Erro na extração: {_sanitize_error(e)}")

    def run_ascii_probe(self):
        """Executa a prova ASCII (busca literal de palavras) e registra no log/report."""
        if not hasattr(self, "original_rom_path") or not self.original_rom_path:
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_select_rom_first"),
            )
            return

        rom_path = self.original_rom_path
        if not os.path.exists(rom_path):
            self.log("[ERROR] ROM não encontrada para prova ASCII.")
            return

        try:
            rom_data = Path(rom_path).read_bytes()
        except Exception as e:
            self.log(f"[ERROR] Falha ao ler ROM: {_sanitize_error(e)}")
            return

        crc32_full = _crc32_file(rom_path)
        rom_size = len(rom_data)

        words = ["WELCOME", "POWER", "TRIES", "SCORE", "TIME"]
        hits = {}
        total_hits = 0

        self.log(f"[START] Prova ASCII | CRC32={crc32_full} | ROM_SIZE={rom_size}")

        for word in words:
            try:
                pattern = word.encode("ascii")
            except UnicodeEncodeError:
                self.log(f"[WARN] Palavra inválida (não ASCII): {word}")
                continue

            offsets = []
            start = 0
            while True:
                idx = rom_data.find(pattern, start)
                if idx == -1:
                    break
                offsets.append(idx)
                start = idx + 1

            hits[word] = offsets
            total_hits += len(offsets)

            if offsets:
                offsets_hex = ", ".join(f"0x{off:06X}" for off in offsets)
                self.log(f"[ASCII] {word} = {len(offsets)} | {offsets_hex}")
            else:
                self.log(f"[ASCII] {word} = 0")

        self.log(f"[ASCII] TOTAL_HITS={total_hits}")

        # Escreve/atualiza report (neutro por CRC32/ROM_SIZE)
        report_dir = self.current_output_dir or os.path.dirname(rom_path)
        report_path = os.path.join(report_dir, f"{crc32_full}_report.txt")
        report_lines = [
            "",
            "-" * 40,
            "ASCII PROBE (LITERAL WORDS)",
            "-" * 40,
            f"CRC32: {crc32_full}",
            f"ROM_SIZE: {rom_size}",
            f"TOTAL_HITS: {total_hits}",
        ]
        for word in words:
            offs = hits.get(word, [])
            if offs:
                offs_hex = ", ".join(f"0x{o:06X}" for o in offs)
                report_lines.append(f"{word}: {len(offs)} [{offs_hex}]")
            else:
                report_lines.append(f"{word}: 0")
        report_lines.append("")

        try:
            mode = "a" if os.path.exists(report_path) else "w"
            with open(report_path, mode, encoding="utf-8") as f:
                f.write("\n".join(report_lines))
        except Exception as e:
            self.log(f"[WARN] Não foi possível escrever report ASCII: {_sanitize_error(e)}")
            return

        # Feedback visível para o usuário
        if total_hits > 0:
            msg = self.tr("ascii_probe_done_message").format(
                count=total_hits, report=report_path
            )
        else:
            msg = self.tr("ascii_probe_done_message_none").format(report=report_path)
        QMessageBox.information(self, self.tr("ascii_probe_done_title"), msg)

    def start_extraction_process(self):
        """Inicia o extrator apropriado baseado na plataforma selecionada."""
        # Calcula CRC32 para naming neutro
        self._extraction_crc32 = _crc32_file(self.original_rom_path)
        rom_size = os.path.getsize(self.original_rom_path)
        self.log(
            f"[START] Preparando extração | CRC32={self._extraction_crc32} | ROM_SIZE={rom_size}"
        )
        self.extract_status_label.setText(self.tr("status_extract_starting"))
        self.extract_progress_bar.setValue(10)

        import subprocess

        # Detecta plataforma pela extensão ou seleção
        file_ext = os.path.splitext(self.original_rom_path)[1].lower()
        selected_platform = (
            self.platform_combo.currentText() if hasattr(self, "platform_combo") else ""
        )

        current_dir = os.path.dirname(os.path.abspath(__file__))

        # ========== SEGA MASTER SYSTEM / MEGA DRIVE ==========
        if file_ext == ".sms" or "Sega Master System" in selected_platform:
            self.log("🎮 Detectado: Sega Master System - Usando Sega Extractor")
            script_path = os.path.join(current_dir, "..", "core", "sega_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(
                    os.path.dirname(current_dir), "core", "sega_extractor.py"
                )
            self._current_extractor_type = "sega"
        elif (
            file_ext in [".md", ".gen", ".bin", ".smd"]
            or "Sega Mega Drive" in selected_platform
        ):
            self.log("🎮 Detectado: Sega Mega Drive/Genesis - Usando Sega Extractor")
            script_path = os.path.join(current_dir, "..", "core", "sega_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(
                    os.path.dirname(current_dir), "core", "sega_extractor.py"
                )
            self._current_extractor_type = "sega"
        else:
            # ========== FALLBACK: FAST CLEAN EXTRACTOR ==========
            script_path = os.path.join(current_dir, "core", "fast_clean_extractor.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(
                    os.path.dirname(current_dir), "core", "fast_clean_extractor.py"
                )
            self._current_extractor_type = "fast_clean"

        if not os.path.exists(script_path):
            self.log("[ERROR] Extrator não encontrado.")
            return

        # 2. Executa o comando
        cmd = f'python "{script_path}" "{self.original_rom_path}"'
        # =========================
        # V6 PRO: SMS/GG/SG usa UniversalMasterSystemExtractor (pipeline principal)
        # =========================
        ext = os.path.splitext(self.original_rom_path)[1].lower()

        # Roteamento SMS/GG/SG para pipeline principal (NUNCA abre janela externa)
        if ext in [".sms", ".gg", ".sg"]:
            """
            Quando a ROM é Master System (.sms), tenta usar o UniversalMasterSystemExtractor
            (que utiliza o banco de dados completo e heurísticas) para extrair todos os textos.
            Caso não esteja disponível ou ocorra um erro, faz fallback para o SegaExtractor
            padrão de ponteiros para manter compatibilidade.
            """
            # Tenta usar o extrator universal se disponível
            if UniversalMasterSystemExtractor:
                self.log(f"🧠 Extração Universal ({ext.upper()}) ativada - CRC32={self._extraction_crc32}")
                try:
                    uni_extractor = UniversalMasterSystemExtractor(
                        self.original_rom_path
                    )
                    total = uni_extractor.extract_all()
                    if total > 0:
                        # Salva resultados na mesma pasta da ROM (gera 4 exports obrigatórios)
                        output_file = uni_extractor.save_results()
                        out_dir = os.path.dirname(output_file)
                        crc32 = uni_extractor.crc32_full
                        self.log(f"[OK] SUCESSO: {total} textos extraídos.")
                        self.log("📁 4 EXPORTS GERADOS:")
                        self.log(f"   • {crc32}_pure_text.jsonl")
                        self.log(f"   • {crc32}_reinsertion_mapping.json")
                        self.log(f"   • {crc32}_report.txt")
                        self.log(f"   • {crc32}_proof.json")
                        self.log(f"📂 Pasta: {out_dir}")
                        # [OK] Guarda o caminho real do arquivo gerado
                        self.extracted_file = output_file
                        self.last_clean_blocks = output_file
                        self.current_rom_crc32 = crc32

                        # Organiza saídas por CRC32 e prepara otimização
                        output_dir = self._organize_crc32_outputs(out_dir, crc32)
                        if output_dir:
                            self.log(
                                self.tr("outputs_organized_message").format(
                                    folder=output_dir
                                )
                            )
                            self._set_extracted_from_output_dir(output_dir, crc32)
                            self._apply_max_extraction(
                                self.original_rom_path, output_dir, crc32
                            )
                            # Limpa arquivos auxiliares gerados após max extraction
                            self._stash_auxiliary_outputs(output_dir, crc32)
                        self.trans_file_label.setText(self._rom_identity_text())
                        self.trans_file_label.setStyleSheet(
                            "color: #cfcfcf; font-weight: bold;"
                        )
                        self.optimize_btn.setEnabled(True)
                        self.log(self.tr("next_step_optimize"))
                        self._update_action_states()

                        self._open_output_select_main(output_dir or out_dir, crc32)
                    else:
                        self.log("[WARN] Universal: Nenhum texto encontrado.")
                    # CORREÇÃO: Finaliza a UI corretamente
                    self.extract_progress_bar.setValue(100)
                    self.extract_status_label.setText(self.tr("status_done"))
                    self.extract_btn.setEnabled(True)
                    return
                except Exception as ex:
                    self.log(
                        f"[ERROR] Erro ao usar UniversalMasterSystemExtractor: {ex}"
                    )
                    # Em caso de erro, continua para fallback abaixo
            # Fallback: usa SegaExtractor e gera os 4 exports obrigatórios
            self.log("🧠 Extração PRO baseada em ponteiros ativada (fallback)")
            try:
                from core.sega_extractor import SegaExtractor
                import json

                sega_extractor = SegaExtractor(self.original_rom_path)
                texts = sega_extractor.extract_texts(min_length=4)
                if not texts:
                    self.log("[WARN] SMS PRO: Nenhum texto confiável encontrado.")
                    self.extract_progress_bar.setValue(100)
                    self.extract_status_label.setText(self.tr("status_done_no_texts"))
                    self.extract_btn.setEnabled(True)
                    return
                self.log(f"[OK] SUCESSO: {len(texts)} strings reais extraídas.")

                # Gera os 4 exports obrigatórios (CRC32 neutro)
                crc32 = self._extraction_crc32
                out_dir = os.path.dirname(self.original_rom_path)

                # 1. pure_text.jsonl
                jsonl_path = os.path.join(out_dir, f"{crc32}_pure_text.jsonl")
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for i, item in enumerate(texts):
                        entry = {
                            "id": i,
                            "offset": item.get("offset_hex", hex(item.get("offset", 0))),
                            "text_src": item.get("text", ""),
                            "max_len_bytes": len(item.get("text", "")) + 1,
                            "encoding": "ascii",
                            "source": "SEGA_POINTER",
                            "reinsertion_safe": item.get("confidence", 0) > 0.6,
                        }
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                # 2. reinsertion_mapping.json
                mapping_path = os.path.join(out_dir, f"{crc32}_reinsertion_mapping.json")
                mapping_entries = []
                for i, item in enumerate(texts):
                    mapping_entries.append({
                        "id": i,
                        "offset": item.get("offset", 0),
                        "max_length": len(item.get("text", "")) + 1,
                        "terminator": 0x00,
                        "source": "SEGA_POINTER",
                        "encoding": "ascii",
                        "reinsertion_safe": item.get("confidence", 0) > 0.6,
                    })
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump({"entries": mapping_entries, "crc32": crc32}, f, indent=2)

                # 3. report.txt
                report_path = os.path.join(out_dir, f"{crc32}_report.txt")
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(f"CRC32: {crc32}\n")
                    f.write(f"ROM_SIZE: {os.path.getsize(self.original_rom_path)}\n")
                    f.write(f"Total Strings: {len(texts)}\n")
                    f.write(f"Extractor: SegaExtractor (fallback)\n")

                # 4. proof.json
                proof_path = os.path.join(out_dir, f"{crc32}_proof.json")
                with open(proof_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "crc32": crc32,
                        "total_strings": len(texts),
                        "extractor": "SegaExtractor",
                        "outputs": [jsonl_path, mapping_path, report_path]
                    }, f, indent=2)

                self.log("📁 4 EXPORTS GERADOS:")
                self.log(f"   • {crc32}_pure_text.jsonl")
                self.log(f"   • {crc32}_reinsertion_mapping.json")
                self.log(f"   • {crc32}_report.txt")
                self.log(f"   • {crc32}_proof.json")
                self.log(f"📂 Pasta: {out_dir}")

                self.extracted_file = jsonl_path
                self.last_clean_blocks = jsonl_path
                self.current_rom_crc32 = crc32

                # Organiza saídas por CRC32 e prepara otimização
                output_dir = self._organize_crc32_outputs(out_dir, crc32)
                if output_dir:
                    self.log(
                        self.tr("outputs_organized_message").format(
                            folder=output_dir
                        )
                    )
                    self._set_extracted_from_output_dir(output_dir, crc32)
                    self._apply_max_extraction(
                        self.original_rom_path, output_dir, crc32
                    )
                    # Limpa arquivos auxiliares gerados após max extraction
                    self._stash_auxiliary_outputs(output_dir, crc32)
                self.trans_file_label.setText(self._rom_identity_text())
                self.trans_file_label.setStyleSheet(
                    "color: #cfcfcf; font-weight: bold;"
                )
                self.optimize_btn.setEnabled(True)
                self.log(self.tr("next_step_optimize"))
                self._update_action_states()

                self._open_output_select_main(output_dir or out_dir, crc32)

                # CORREÇÃO: Finaliza a UI corretamente
                self.extract_progress_bar.setValue(100)
                self.extract_status_label.setText(self.tr("status_done"))
                self.extract_btn.setEnabled(True)
                return
            except Exception as ex2:
                self.log(f"[ERROR] Erro ao usar SegaExtractor: {ex2}")
                self.extract_progress_bar.setValue(100)
                self.extract_status_label.setText(self.tr("status_error"))
                self.extract_btn.setEnabled(True)
                return

        try:
            self.log(
                "[START] Rodando extrator... (Aguarde)"
            )
            # Guarda o processo numa variável self.current_process para monitorar
            self.current_process = subprocess.Popen(cmd, shell=True)

            self.extract_progress_bar.setValue(50)
            self.extract_status_label.setText(self.tr("status_processing"))

            # 3. CRIA O MONITOR (O Segredo para não travar)
            self.v9_timer = QTimer()
            self.v9_timer.timeout.connect(self.check_v9_status)
            self.v9_timer.start(1000)  # Verifica a cada 1 segundo (1000ms)

        except Exception as e:
            self.log(f"[ERROR] Erro ao lançar: {_sanitize_error(e)}")

    def check_v9_status(self):
        """Verifica se o processo de extração terminou e lê o relatório para o log."""
        if hasattr(self, "current_process") and self.current_process.poll() is not None:
            self.v9_timer.stop()
            self.extract_progress_bar.setValue(100)
            self.extract_status_label.setText(self.tr("status_done"))

            # --- LÓGICA DE RECUPERAÇÃO DE RESULTADOS (NEUTRAL) ---
            rom_dir = os.path.dirname(self.original_rom_path)
            crc32_id = getattr(self, "_extraction_crc32", None)
            if not crc32_id:
                crc32_id = _crc32_file(self.original_rom_path)

            # Report file com naming neutro (CRC32)
            report_file = os.path.join(rom_dir, f"{crc32_id}_report.txt")

            # Verifica qual extrator foi usado e procura o arquivo correto
            extractor_type = getattr(self, "_current_extractor_type", "fast_clean")

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
                self.log("=" * 40)
                self.log("📋 RESUMO DA EXTRAÇÃO:")
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip() and not line.startswith("#"):
                                self.log(f"  {line.strip()}")
                except Exception as e:
                    self.log(f"[WARN] Erro ao ler relatório: {_sanitize_error(e)}")
                self.log("=" * 40)

            # 2. Tenta mostrar uma prévia das strings no log
            if extracted_file:
                self.extracted_file = extracted_file
                self.current_rom_crc32 = crc32_id
                output_dir = self._organize_crc32_outputs(rom_dir, crc32_id)
                if output_dir:
                    self.log(
                        self.tr("outputs_organized_message").format(folder=output_dir)
                    )
                    self._set_extracted_from_output_dir(output_dir, crc32_id)
                    self._apply_max_extraction(
                        self.original_rom_path, output_dir, crc32_id
                    )
                    extracted_file = self.extracted_file or extracted_file
                file_size = os.path.getsize(extracted_file)
                self.trans_file_label.setText(f"TXT ({file_size} bytes)")
                self.trans_file_label.setStyleSheet(
                    "color: #cfcfcf; font-weight: bold;"
                )

                # Conta quantas linhas tem
                try:
                    with open(extracted_file, "r", encoding="utf-8") as f:
                        linhas = f.readlines()
                        total = len(
                            [
                                l
                                for l in linhas
                                if l.startswith("[0x") or l.startswith("{")
                            ]
                        )
                        self.log(f"[OK] SUCESSO: {total} strings reais extraídas.")

                        # Mostra as 5 primeiras para dar um "gosto" no log
                        self.log("🔍 PRÉVIA DOS TEXTOS:")
                        amostra = [
                            l.strip()
                            for l in linhas
                            if l.startswith("[0x") or l.startswith("{")
                        ][:5]
                        for a in amostra:
                            self.log(f"   {a}")
                except (OSError, UnicodeError):
                    pass

                self.optimize_btn.setEnabled(True)
                self.log(self.tr("next_step_optimize"))
                platform_name = "Sega" if extractor_type == "sega" else "ROM"
                QMessageBox.information(
                    self,
                    self.tr("extraction_finished_title"),
                    self.tr("extraction_finished_message").format(
                        platform=platform_name, crc=crc32_id, total=total
                    ),
                )
            else:
                self.log("[ERROR] ERRO: O arquivo extraído não foi gerado.")

    def run_batch_test(self):
        """Executa teste comparativo V 9.5 em múltiplas ROMs"""
        from PyQt6.QtWidgets import QMessageBox

        self.log("🧪 Iniciando Teste em Lote V9.5...")

        # Mostra diálogo de confirmação
        reply = QMessageBox.question(
            self,
            self.tr("batch_test_title"),
            self.tr("batch_test_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            self.log("[ERROR] Teste em lote cancelado pelo usuário.")
            return

        # Desabilita botões durante o processo
        self.batch_test_btn.setEnabled(False)
        self.extract_btn.setEnabled(False)
        self.optimize_btn.setEnabled(False)

        self.extract_status_label.setText(self.tr("status_batch_running"))
        self.extract_progress_bar.setValue(10)

        # Localiza o script de teste em lote
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        batch_script = os.path.join(project_root, "test_v9_batch.py")

        if not os.path.exists(batch_script):
            self.log(
                f"[ERROR] ERRO: Script test_v9_batch.py não encontrado em {batch_script}"
            )
            QMessageBox.critical(
                self,
                self.tr("dialog_title_error"),
                self.tr("batch_script_not_found").format(path=batch_script),
            )
            self.batch_test_btn.setEnabled(True)
            self.extract_btn.setEnabled(True)
            self.optimize_btn.setEnabled(True)
            return

        try:
            self.log("[START] Executando teste em lote...")
            self.log("⏳ Aguarde... O processo pode demorar alguns minutos.")

            # Executa o script de forma assíncrona
            self.batch_process = subprocess.Popen(
                [sys.executable, batch_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Cria timer para monitorar o processo
            self.batch_timer = QTimer()
            self.batch_timer.timeout.connect(self.check_batch_status)
            self.batch_timer.start(1000)  # Verifica a cada 1 segundo

            self.extract_progress_bar.setValue(50)

        except Exception as e:
            self.log(f"[ERROR] Erro ao iniciar teste em lote: {_sanitize_error(e)}")
            QMessageBox.critical(
                self,
                self.tr("dialog_title_error"),
                self.tr("batch_start_error").format(error=str(e)),
            )
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
                self.extract_status_label.setText(self.tr("status_batch_done"))
                self.log("[OK] Teste em lote V 9.5 concluído com sucesso!")

                # Procura pelo arquivo de relatório
                project_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                results_dir = os.path.join(project_root, "resultados_v9_comparativo")

                if os.path.exists(results_dir):
                    # Pega o relatório mais recente
                    reports = sorted(
                        [
                            f
                            for f in os.listdir(results_dir)
                            if f.startswith("relatorio_comparativo_v9_")
                        ],
                        reverse=True,
                    )

                    if reports:
                        latest_report = os.path.join(results_dir, reports[0])
                        self.log(f"[STATS] Relatório gerado: {reports[0]}")

                        # Mostra mensagem de sucesso com opção de abrir relatório
                        reply = QMessageBox.question(
                            self,
                            self.tr("dialog_title_success"),
                            self.tr("batch_report_question").format(dir=results_dir),
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )

                        if reply == QMessageBox.StandardButton.Yes:
                            import platform

                            if platform.system() == "Windows":
                                os.startfile(latest_report)
                            elif platform.system() == "Darwin":  # macOS
                                subprocess.Popen(["open", latest_report])
                            else:  # Linux
                                subprocess.Popen(["xdg-open", latest_report])
                    else:
                        QMessageBox.information(
                            self,
                            self.tr("dialog_title_done"),
                            self.tr("batch_done_no_report"),
                        )
                else:
                    QMessageBox.information(
                        self, self.tr("dialog_title_done"), self.tr("batch_done_generic")
                    )
            else:
                self.extract_progress_bar.setValue(0)
                self.extract_status_label.setText(self.tr("status_batch_error"))
                self.log(
                    f"[ERROR] Erro no teste em lote (código {self.batch_process.returncode})"
                )
                if stderr:
                    self.log(f"Erro: {stderr}")

                QMessageBox.critical(
                    self,
                    self.tr("dialog_title_error"),
                    self.tr("batch_error_message"),
                )

            # Reabilita botões
            self.batch_test_btn.setEnabled(True)
            self.extract_btn.setEnabled(True)
            self.optimize_btn.setEnabled(True)

    def optimize_data(self):
        if not self.original_rom_path:
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_no_rom_selected"),
            )
            return

        # [OK] Usa o arquivo real gerado pela extração
        rom_filename = self.current_rom_crc32 or os.path.splitext(
            os.path.basename(self.original_rom_path)
        )[0]

        input_file = None
        for attr in ("last_clean_blocks", "extracted_file"):
            p = getattr(self, attr, None)
            if p and os.path.exists(p):
                input_file = p
                break

        # Fallback: usa JSONL principal (se for o único arquivo visível)
        if not input_file:
            output_dir = self.current_output_dir
            if output_dir and self.current_rom_crc32:
                if self.max_extraction_mode:
                    all_text = os.path.join(
                        output_dir,
                        "_interno",
                        f"{self.current_rom_crc32}_all_text.jsonl",
                    )
                    if os.path.exists(all_text):
                        input_file = all_text
                if not input_file:
                    jsonl = os.path.join(
                        output_dir, f"{self.current_rom_crc32}_pure_text.jsonl"
                    )
                    if os.path.exists(jsonl):
                        input_file = jsonl

        # Fallback: tenta achar automaticamente na pasta texts do projeto
        if not input_file:
            try:
                texts_dir = os.path.join(project_root, "texts")
                if os.path.isdir(texts_dir):
                    candidates = []
                    for root, _, files in os.walk(texts_dir):
                        for fn in files:
                            if fn in (
                                f"{rom_filename}_clean_blocks.txt",
                                f"{rom_filename}_extracted.txt",
                            ):
                                candidates.append(os.path.join(root, fn))
                    if candidates:
                        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        input_file = candidates[0]
            except Exception:
                pass

        if not input_file:
            QMessageBox.warning(
                self,
                self.tr("dialog_title_error"),
                self.tr("error_extraction_file_not_found").format(
                    rom=self._rom_identity_text(), action=self.tr("extract_texts")
                ),
            )
            return

        self.extracted_file = input_file  # Atualiza para as próximas etapas
        self.optimize_status_label.setText(self.tr("status_analyzing"))
        self.optimize_progress_bar.setValue(0)
        self.optimize_btn.setEnabled(False)

        # [OK] PASSA AS CONFIGURAÇÕES DO OTIMIZADOR V 9.5
        self.optimize_thread = OptimizationWorker(
            input_file, is_pc_game=False, config=self.optimizer_config
        )
        self.optimize_thread.progress_signal.connect(
            self.optimize_progress_bar.setValue
        )
        self.optimize_thread.status_signal.connect(
            lambda text: self._set_status_label(self.optimize_status_label, text)
        )
        self.optimize_thread.log_signal.connect(self.log)
        self.optimize_thread.finished_signal.connect(self.on_optimization_finished)
        self.optimize_thread.error_signal.connect(self.on_optimization_error)
        self.optimize_thread.start()

    def on_optimization_finished(self, output_file: str):
        self.optimized_file = output_file
        crc32_full = self.current_rom_crc32 or Path(output_file).name.split("_", 1)[0]
        self._organize_crc32_outputs(os.path.dirname(output_file), crc32_full)
        self.trans_file_label.setText(self._rom_identity_text())
        self.trans_file_label.setStyleSheet("color: #cfcfcf; font-weight: bold;")
        self.optimize_btn.setEnabled(True)
        self.tabs.setTabEnabled(2, True)
        self._update_action_states()

        # Recarrega o arquivo otimizado e atualiza o contador de linhas
        try:
            optimized_path = self.optimized_file or output_file
            with open(optimized_path, "r", encoding="utf-8", errors="ignore") as f:
                optimized_lines = f.readlines()

            line_count = len(optimized_lines)
            self.log(f"[STATS] Arquivo otimizado carregado: {line_count:,} linhas")

            # Atualiza interface para mostrar o novo arquivo
            self.optimize_status_label.setText(
                self.tr("status_done_with_lines").format(count=f"{line_count:,}")
            )

        except Exception as e:
            self.log(f"[WARN] Erro ao contar linhas: {_sanitize_error(e)}")

        QMessageBox.information(
            self,
            self.tr("dialog_title_success"),
            self.tr("optimization_completed_next_message").format(
                file=self._rom_identity_text(), lines=f"{line_count:,}"
            ),
        )

    def on_optimization_error(self, error_msg: str):
        self.optimize_status_label.setText(self.tr("status_error"))
        self.optimize_btn.setEnabled(True)
        self.log(f"[ERROR] Erro na otimização: {error_msg}")
        QMessageBox.critical(
            self,
            self.tr("dialog_title_error"),
            self.tr("optimization_error_message").format(error=error_msg),
        )

    def on_extract_finished(self, success: bool, message: str):
        if success:
            self.extract_status_label.setText(self.tr("status_done"))
            self.extract_progress_bar.setValue(100)

            try:
                rom_name = os.path.basename(self.original_rom_path).rsplit(".", 1)[0]
                rom_dir = os.path.dirname(self.original_rom_path)
                extracted_file_path = os.path.join(
                    rom_dir, f"{rom_name}_extracted_texts.txt"
                )

                if os.path.exists(extracted_file_path):
                    self.extracted_file = extracted_file_path
                    # Organiza outputs por CRC32 (evita bagunça na pasta)
                    crc32_full = self.current_rom_crc32 or _crc32_file(
                        self.original_rom_path
                    )
                    output_dir = self._organize_crc32_outputs(
                        rom_dir, crc32_full
                    )
                    if output_dir:
                        moved_path = os.path.join(
                            output_dir, os.path.basename(extracted_file_path)
                        )
                        if os.path.exists(moved_path):
                            self.extracted_file = moved_path
                        self.log(
                            self.tr("outputs_organized_message").format(
                                folder=output_dir
                            )
                        )
                        self._set_extracted_from_output_dir(output_dir, crc32_full)
                        self._apply_max_extraction(
                            self.original_rom_path, output_dir, crc32_full
                        )
                    self.trans_file_label.setText(self._rom_identity_text())
                    self.trans_file_label.setStyleSheet(
                        "color: #cfcfcf; font-weight: bold;"
                    )
                    self.log(
                        "[OK] Extraction completed successfully. Ready for Optimization."
                    )
                    self.optimize_btn.setEnabled(True)
                    self.log(self.tr("next_step_optimize"))
                else:
                    # Fallback para saída padrão CRC32_pure_text.jsonl
                    crc32_full = self.current_rom_crc32 or _crc32_file(
                        self.original_rom_path
                    )
                    output_dir = self._organize_crc32_outputs(rom_dir, crc32_full)
                    self._set_extracted_from_output_dir(
                        output_dir or rom_dir, crc32_full
                    )
                    if output_dir:
                        self._apply_max_extraction(
                            self.original_rom_path, output_dir, crc32_full
                        )
                    if self.extracted_file and os.path.exists(self.extracted_file):
                        self.trans_file_label.setText(self._rom_identity_text())
                        self.trans_file_label.setStyleSheet(
                            "color: #cfcfcf; font-weight: bold;"
                        )
                        if output_dir:
                            self.log(
                                self.tr("outputs_organized_message").format(
                                    folder=output_dir
                                )
                            )
                        self.optimize_btn.setEnabled(True)
                        self.log(self.tr("next_step_optimize"))
                    else:
                        self.log("[ERROR] Arquivo extraído não encontrado.")
                        self.optimize_btn.setEnabled(False)

            except Exception as e:
                self.log(f"[ERROR] Error loading file: {_sanitize_error(e)}")
                self.optimize_btn.setEnabled(False)
        else:
            self.extract_status_label.setText(self.tr("status_error"))
            self.log(f"[ERROR] Extraction failed: {message}")
            self.optimize_btn.setEnabled(False)
            QMessageBox.critical(
                self,
                self.tr("dialog_title_error"),
                self.tr("extraction_failed_message").format(message=message),
            )
        self._update_action_states()

    def on_fast_extract_finished(self, results: dict):
        """Callback quando ULTIMATE EXTRACTION SUITE V 9.5 PRO termina."""
        self.extract_status_label.setText(self.tr("status_done"))
        self.extract_progress_bar.setValue(100)

        try:
            # Pega caminho do arquivo gerado
            output_file = results.get("output_file")

            if output_file and os.path.exists(output_file):
                self.extracted_file = output_file
                # Organiza outputs por CRC32 (evita bagunça na pasta)
                crc32_full = (
                    self.current_rom_crc32
                    or Path(output_file).name.split("_", 1)[0]
                )
                output_dir = self._organize_crc32_outputs(
                    os.path.dirname(output_file), crc32_full
                )
                if output_dir:
                    moved_path = os.path.join(output_dir, os.path.basename(output_file))
                    if os.path.exists(moved_path):
                        self.extracted_file = moved_path
                    self.log(
                        self.tr("outputs_organized_message").format(folder=output_dir)
                    )
                    self._set_extracted_from_output_dir(output_dir, crc32_full)
                    self._apply_max_extraction(
                        self.original_rom_path, output_dir, crc32_full
                    )
                self.trans_file_label.setText(self._rom_identity_text())
                self.trans_file_label.setStyleSheet(
                    "color: #cfcfcf; font-weight: bold;"
                )

                # Log estatísticas V7.0
                valid_strings = results.get("valid_strings", 0)
                recovered_strings = results.get("recovered_strings", 0)
                total_strings = results.get(
                    "total_strings", valid_strings + recovered_strings
                )
                approval_rate = results.get("approval_rate", 0)
                pattern_engine_used = results.get("pattern_engine_used", False)

                self.log("[OK] NEUROROM AI V 6.0 PRO SUITE: Extração concluída!")
                self.log(f"[STATS] Strings principais: {valid_strings}")
                if recovered_strings > 0:
                    self.log(f"🔍 Strings recuperadas: {recovered_strings}")
                self.log(f"🎉 Total extraído: {total_strings}")
                self.log(f"📈 Taxa de aprovação: {approval_rate:.1f}%")
                if pattern_engine_used:
                    self.log("🔬 Pattern Engine ativado - tabela detectada!")
                self.log("📂 Arquivo salvo.")

                # Habilita otimização (opcional neste caso, pois já está filtrado)
                self.optimize_btn.setEnabled(True)

                # Mostra mensagem de sucesso
                msg = self.tr("fast_extract_success_message").format(
                    valid=valid_strings,
                    recovered=recovered_strings,
                    total=total_strings,
                    approval=f"{approval_rate:.1f}%",
                    file=self._rom_identity_text(),
                )

                QMessageBox.information(
                    self, self.tr("dialog_title_success"), msg
                )
                self.log(self.tr("next_step_optimize"))
            else:
                self.log("[ERROR] Arquivo não encontrado.")
                self.optimize_btn.setEnabled(False)

        except Exception as e:
            self.log(f"[ERROR] Erro ao processar resultado: {_sanitize_error(e)}")
            self.optimize_btn.setEnabled(False)
        self._update_action_states()

    def on_fast_extract_error(self, error_msg: str):
        """Callback quando ocorre erro na extração."""
        self.extract_status_label.setText(self.tr("status_error"))
        self.log(f"[ERROR] Erro na extração: {error_msg}")
        self.optimize_btn.setEnabled(False)
        QMessageBox.critical(
            self,
            self.tr("dialog_title_error"),
            self.tr("fast_extraction_failed_message").format(error=error_msg),
        )
        self._update_action_states()

    def translate_texts(self):
        input_file = self.optimized_file
        tilemap_jsonl = self._resolve_tilemap_jsonl_for_translation(input_file)
        tilemap_mode = bool(tilemap_jsonl)

        if (not input_file or not os.path.exists(input_file)) and not tilemap_mode:
            QMessageBox.warning(
                self,
                self.tr("dialog_title_warning"),
                self.tr("warn_select_optimized_file"),
            )
            return

        if tilemap_mode:
            input_file = tilemap_jsonl
            self.log(
                "🧩 Tilemap detectado: tradução será feita direto do JSONL (sem Otimizar Dados)."
            )

        mode_index = self.mode_combo.currentIndex()
        mode_text = self.mode_combo.currentText()

        # Verifica se modo requer API key (AUTO, Gemini e ChatGPT precisam)
        needs_api_key = mode_index in [0, 1, 3]  # AUTO, Gemini ou ChatGPT

        if needs_api_key:
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                if tilemap_mode:
                    # Tilemap: fallback automático para Ollama
                    self.log("⚠️ API key ausente. Tilemap será traduzido com Ollama local.")
                    mode_index = 2
                    api_key = ""
                elif mode_index in [0, 1]:  # AUTO ou Gemini
                    QMessageBox.warning(
                        self,
                        self.tr("dialog_title_warning"),
                        self.tr("api_key_gemini_required"),
                    )
                    return
                else:
                    QMessageBox.warning(
                        self,
                        self.tr("dialog_title_warning"),
                        self.tr("api_key_openai_required"),
                    )
                    return
        else:
            api_key = ""

        self.translate_btn.setEnabled(False)
        self.stop_translation_btn.setEnabled(True)  # Habilita botão PARAR
        self.translation_progress_bar.setValue(0)
        self.translation_status_label.setText(
            self.tr("status_translation_starting_worker")
        )

        target_lang_name = self.target_lang_combo.currentText()

        # Escolhe Worker baseado no modo (tilemap tem pipeline próprio)
        if tilemap_mode:
            use_gemini = mode_index in [0, 1] and api_key and gemini_api and gemini_api.GENAI_AVAILABLE
            if use_gemini:
                self.log("🧩 Tilemap: Gemini (JSONL direto) iniciado.")
            else:
                if mode_index == 3:
                    self.log("⚠️ Tilemap: ChatGPT não suportado. Usando Ollama local.")
                self.log("🧩 Tilemap: Ollama (JSONL direto) iniciado.")
            self.translate_thread = TilemapWorker(
                input_file,
                target_lang_name,
                api_key=api_key,
                prefer_gemini=use_gemini,
            )
        else:
            if mode_index == 0:  # AUTO (Gemini + Ollama)
                self.log("🤖 AUTO: Gemini primeiro, Ollama se quota esgotar.")
                self.translate_thread = HybridWorker(api_key, input_file, target_lang_name)
            elif mode_index == 1:  # Gemini (Google AI)
                self.log("⚡ Gemini (Google AI): iniciado.")
                self.translate_thread = GeminiWorker(api_key, input_file, target_lang_name)
            elif mode_index == 2:  # Llama (Ollama Local)
                self.log("🦙 Llama (Ollama Local): iniciado.")
                self.translate_thread = OllamaWorker(input_file, target_lang_name)
            elif mode_index == 3:  # ChatGPT (OpenAI)
                self.log("🤖 ChatGPT (OpenAI): iniciado.")
                self.translate_thread = ChatGPTWorker(api_key, input_file, target_lang_name)
            else:
                QMessageBox.information(
                    self,
                    self.tr("dialog_title_info"),
                    self.tr("mode_not_implemented").format(mode=mode_text),
                )
                self.translate_btn.setEnabled(True)
                self.stop_translation_btn.setEnabled(False)
                return

        self.translate_thread.progress_signal.connect(
            self.translation_progress_bar.setValue
        )
        self.translate_thread.status_signal.connect(
            lambda text: self._set_status_label(self.translation_status_label, text)
        )
        self.translate_thread.log_signal.connect(self.log)
        self.translate_thread.finished_signal.connect(self.on_gemini_finished)
        self.translate_thread.error_signal.connect(self.on_gemini_error)
        self.translate_thread.realtime_signal.connect(self.update_realtime_panel)
        self.translate_thread.start()

    def stop_translation(self):
        """Para a tradução em andamento"""
        if (
            hasattr(self, "translate_thread")
            and self.translate_thread
            and self.translate_thread.isRunning()
        ):
            reply = QMessageBox.question(
                self,
                self.tr("dialog_title_confirm"),
                self.tr("confirm_stop_translation"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.log("🛑 Parando tradução...")
                self.translate_thread.stop()  # Chama método stop() do worker
                self.translate_thread.wait()  # Aguarda thread terminar
                self.translation_status_label.setText(
                    self.tr("status_translation_stopped")
                )
                self.translate_btn.setEnabled(True)
                self.stop_translation_btn.setEnabled(False)
                self.log("[OK] Tradução parada. Progresso parcial foi salvo.")

    def on_gemini_finished(self, output_file: str):
        self.translation_progress_bar.setValue(100)
        self.translation_status_label.setText(self.tr("status_translation_done"))
        self.log("Translation saved.")

        self.translated_file = output_file
        crc32_full = self.current_rom_crc32 or Path(output_file).name.split("_", 1)[0]
        self._organize_crc32_outputs(os.path.dirname(output_file), crc32_full)
        self.translated_file_label.setText(self._rom_identity_text())
        self.translated_file_label.setStyleSheet("color:#cfcfcf;font-weight:bold;")

        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        self.tabs.setTabEnabled(3, True)  # Reinserção agora no índice 3
        self._update_action_states()
        self.run_auto_graphics_pipeline()
        QMessageBox.information(
            self,
            self.tr("congratulations_title"),
            self.tr("translation_completed_next_message"),
        )
        self.log(self.tr("next_step_reinsert"))
        # Abre Explorer selecionando o arquivo traduzido
        self._explorer_select(output_file, os.path.dirname(output_file))

    def on_gemini_error(self, error_msg: str):
        self.translation_status_label.setText(self.tr("status_translation_fatal"))
        self.log(f"Translation error: {error_msg}")
        self.translate_btn.setEnabled(True)
        self.stop_translation_btn.setEnabled(False)  # Desabilita botão PARAR
        QMessageBox.critical(
            self,
            self.tr("dialog_title_error"),
            self.tr("translation_error_message").format(error=error_msg),
        )

    def update_realtime_panel(self, original: str, translated: str, translator: str):
        """Atualiza painel de tradução em tempo real"""
        # Trunca textos longos para caber no painel
        max_len = 80
        orig_display = (
            original[:max_len] + "..." if len(original) > max_len else original
        )
        trans_display = (
            translated[:max_len] + "..." if len(translated) > max_len else translated
        )

        self.realtime_original_label.setText(
            self.tr("realtime_original_prefix").format(text=orig_display)
        )
        self.realtime_translated_label.setText(
            self.tr("realtime_translated_prefix").format(text=trans_display)
        )
        self.realtime_info_label.setText(
            self.tr("realtime_info_prefix").format(translator=translator)
        )

    def _translate_status_text(self, text: str) -> str:
        """Normaliza mensagens de status para o idioma atual."""
        if not text:
            return text

        mapping = {
            "Concluído!": self.tr("status_done"),
            "Concluído (sem textos)": self.tr("status_done_no_texts"),
            "Erro!": self.tr("status_error"),
            "Processando...": self.tr("status_processing"),
            "Iniciando extração...": self.tr("status_extract_starting"),
            "Preparando arquivos...": self.tr("status_reinsertion_preparing"),
            "Executando teste em lote...": self.tr("status_batch_running"),
            "Teste em lote concluído!": self.tr("status_batch_done"),
            "Erro no teste em lote": self.tr("status_batch_error"),
            "Analyzing...": self.tr("status_analyzing"),
            "Starting Worker...": self.tr("status_translation_starting_worker"),
            "[ERROR] Parado pelo usuário": self.tr("status_translation_stopped"),
            "Erro Fatal": self.tr("status_translation_fatal"),
            "Completed!": self.tr("status_done"),
            "Completed (no texts)": self.tr("status_done_no_texts"),
            "Error!": self.tr("status_error"),
            "Processing...": self.tr("status_processing"),
            "Preparing files...": self.tr("status_reinsertion_preparing"),
            "Running batch test...": self.tr("status_batch_running"),
            "Batch test completed!": self.tr("status_batch_done"),
            "Batch test error": self.tr("status_batch_error"),
        }
        if text in mapping:
            return mapping[text]

        match = re.match(r"^Concluído! \\(([^)]+) linhas\\)$", text)
        if match:
            return self.tr("status_done_with_lines").format(count=match.group(1))

        match = re.match(r"^Completed! \\(([^)]+) lines\\)$", text)
        if match:
            return self.tr("status_done_with_lines").format(count=match.group(1))

        return text

    def _set_status_label(self, label: QLabel, text: str) -> None:
        """Aplica texto de status traduzido em um QLabel."""
        if label is None:
            return
        label.setText(self._translate_status_text(text))

    def restart_application(self):
        self.log("Reiniciando aplicação...")
        self.save_config()
        self.cleanup_threads()

        python = sys.executable
        script = sys.argv[0]
        if sys.platform == "win32":
            subprocess.Popen(
                [python, script], creationflags=subprocess.CREATE_NEW_CONSOLE
            )
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
            if getattr(self, "original_rom_path", None) and self.current_rom_crc32:
                try:
                    rom_name = Path(self.original_rom_path).name
                    message = message.replace(rom_name, f"CRC32={self.current_rom_crc32}")
                except Exception:
                    pass

            # Verifica se o painel de log existe
            if hasattr(self, "log_text") and self.log_text is not None:
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
        if hasattr(self, "gfx_log_text"):
            self.gfx_log_text.append(f"{timestamp} {message}")
            scrollbar = self.gfx_log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        # Senão, usa o log principal
        elif hasattr(self, "log_text"):
            self.log_text.append(f"{timestamp} {message}")
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def on_source_language_changed(self, language_name: str):
        """Update source language when user changes selection."""
        # Find corresponding language code
        for name, code in ProjectConfig.SOURCE_LANGUAGES.items():
            if name == language_name:
                self.source_language_code = code
                self.source_language_name = name
                if not getattr(self, "_startup", False) and not getattr(
                    self, "_suppress_lang_logs", False
                ):
                    self.log(f"[LANG] Source language: {name} ({code})")
                break

    def on_target_language_changed(self, language_name: str):
        """Update target language when user changes selection."""
        # Find corresponding language code
        for name, code in ProjectConfig.TARGET_LANGUAGES.items():
            if name == language_name:
                self.target_language_code = code
                self.target_language_name = name
                if not getattr(self, "_startup", False) and not getattr(
                    self, "_suppress_lang_logs", False
                ):
                    self.log(f"[LANG] Target language: {name} ({code})")
                break

    def open_inventory_doc(self):
        """Abre o inventário completo dentro da Ajuda."""
        self.show_inventory_dialog()

    def show_inventory_dialog(self):
        """Exibe o inventário completo dentro da interface."""
        inventory_path = ProjectConfig.FRAMEWORK_DIR / "docs" / "INVENTARIO_COMPLETO.md"
        if not inventory_path.exists():
            QMessageBox.warning(
                self,
                self.tr("dialog_title_error"),
                self.tr("inventory_missing_message").format(path=str(inventory_path)),
            )
            return
        try:
            content = inventory_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("dialog_title_error"),
                f"{self.tr('inventory_open_failed')}\\n{_sanitize_error(e)}",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("inventory_title"))
        dialog.setMinimumSize(900, 700)
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

        layout = QVBoxLayout(dialog)
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText(content)
        text_area.setFont(QFont("Consolas", 10))
        if self.is_rtl_language():
            text_area.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            text_area.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(text_area)

        reload_btn = QPushButton(self.tr("btn_update_guide"))
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _reload_inventory():
            try:
                text_area.setPlainText(
                    inventory_path.read_text(encoding="utf-8", errors="replace")
                )
            except Exception:
                pass

        reload_btn.clicked.connect(_reload_inventory)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(reload_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

        dialog.exec()

    def show_quick_help_dialog(self):
        """Exibe um resumo rápido do sistema e atalho para o inventário completo."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("welcome_title"))
        dialog.setMinimumSize(700, 520)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        content_label = QLabel(self.tr("welcome_body"))
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.PlainText)
        content_label.setFont(QFont("Segoe UI", 11))
        self._apply_rtl_label(content_label)
        content_layout.addWidget(content_label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

        dialog.exec()

    def show_quick_help(self):
        """Ajuda rápida: mostra apenas a tela de boas-vindas."""
        self.show_quick_help_dialog()

    def start_guided_tour(self):
        """Tour guiado completo (5 passos)."""
        self.show_onboarding_tour(True)

    def show_visual_guide(self):
        """Exibe guia visual com passos e screenshots (se existirem)."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("visual_guide_title"))
        dialog.setMinimumSize(820, 620)

        layout = QVBoxLayout(dialog)
        intro = QLabel(self.tr("visual_guide_intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b0b0b0; padding: 6px;")
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(14)

        base_dir = Path(project_root) / "docs" / "ajuda_visual"
        try:
            rel_base = os.path.relpath(base_dir, project_root)
        except Exception:
            rel_base = str(base_dir)
        steps = [
            ("visual_step_1_title", "visual_step_1_body", "step1_extracao.png"),
            ("visual_step_2_title", "visual_step_2_body", "step2_otimizacao.png"),
            ("visual_step_3_title", "visual_step_3_body", "step3_traducao.png"),
            ("visual_step_4_title", "visual_step_4_body", "step4_reinsercao.png"),
        ]

        for title_key, body_key, image_name in steps:
            group = QGroupBox(self.tr(title_key))
            group_layout = QVBoxLayout()
            body = QLabel(self.tr(body_key))
            body.setWordWrap(True)
            body.setStyleSheet("color: #cfcfcf; padding: 4px;")
            group_layout.addWidget(body)

            img_path = base_dir / image_name
            rel_img = f"{rel_base}\\{image_name}"
            if img_path.exists():
                pix = QPixmap(str(img_path))
                img = QLabel()
                img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img.setPixmap(
                    pix.scaledToWidth(
                        760, Qt.TransformationMode.SmoothTransformation
                    )
                )
                img.setStyleSheet("padding: 6px;")
                group_layout.addWidget(img)
            else:
                placeholder = QLabel(
                    self.tr("visual_image_missing").format(path=rel_img)
                )
                placeholder.setWordWrap(True)
                placeholder.setStyleSheet(
                    "border: 1px dashed #555; color: #888; padding: 10px;"
                )
                group_layout.addWidget(placeholder)

            group.setLayout(group_layout)
            content_layout.addWidget(group)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        path_label = QLabel(
            self.tr("visual_images_path").format(path=rel_base)
        )
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(path_label)

        buttons = QHBoxLayout()
        open_btn = QPushButton(self.tr("visual_open_folder"))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(base_dir)))
        )
        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(open_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        dialog.exec()

    def show_onboarding_tour(self, force: bool = False):
        """Mostra um tour rápido com dicas essenciais."""
        if not force and getattr(self, "onboarding_shown", False):
            return

        steps = [
            ("tour_step_1_title", "tour_step_1_body"),
            ("tour_step_2_title", "tour_step_2_body"),
            ("tour_step_3_title", "tour_step_3_body"),
            ("tour_step_4_title", "tour_step_4_body"),
            ("tour_step_5_title", "tour_step_5_body"),
        ]

        for idx, (title_key, body_key) in enumerate(steps):
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            if idx == 0:
                msg.setWindowTitle(self.tr("welcome_title"))
                msg.setText(self.tr("welcome_body"))
                msg.setTextFormat(Qt.TextFormat.PlainText)
            else:
                msg.setWindowTitle(self.tr(title_key))
                msg.setText(self.tr(body_key))
                msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            try:
                app = QApplication.instance()
                if app:
                    msg.setStyleSheet(app.styleSheet())
            except Exception:
                pass
            msg.setLayoutDirection(
                Qt.LayoutDirection.RightToLeft
                if self.is_rtl_language()
                else Qt.LayoutDirection.LeftToRight
            )

            next_label = (
                self.tr("tour_finish")
                if idx == len(steps) - 1
                else self.tr("tour_next")
            )
            btn_next = msg.addButton(next_label, QMessageBox.ButtonRole.AcceptRole)
            btn_skip = msg.addButton(self.tr("tour_skip"), QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_skip:
                break
            if msg.clickedButton() != btn_next:
                break

        self.onboarding_shown = True
        self.save_config()

    def show_manual_step(self, index: int):
        """COMMERCIAL GRADE: Display manual instructions in professional popup."""
        if index == 0:
            return
        if hasattr(self, "manual_combo") and self.manual_combo is not None:
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
            "manual_step_4_title",
        ]

        step_content_keys = [
            "manual_step_1_content",
            "manual_step_2_content",
            "manual_step_3_content",
            "manual_step_4_content",
        ]

        step_title = self.tr(step_title_keys[index - 1])
        step_content = self.tr(step_content_keys[index - 1])

        dialog = QDialog(self)
        dialog.setWindowTitle(step_title)
        dialog.setMinimumSize(700, 600)
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

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
        self._apply_rtl_label(content_label)
        content_layout.addWidget(content_label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        def _reload_guide():
            # Força releitura do arquivo de idioma para pegar mudanças no texto
            ProjectConfig.clear_translations_cache(self.current_ui_lang)
            dialog.setWindowTitle(self.tr(step_title_keys[index - 1]))
            content_label.setText(self.tr(step_content_keys[index - 1]))

        reload_btn = QPushButton(self.tr("btn_update_guide"))
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.clicked.connect(_reload_guide)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        close_btn.clicked.connect(dialog.accept)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(reload_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

        dialog.exec()

    def show_graphics_guide(self):
        """Exibe o manual com tradução dinâmica baseada no idioma selecionado."""
        dialog = QDialog(self)
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

        # TÍTULO TRADUZIDO DINAMICAMENTE
        self.setWindowTitle(
            "NeuroROM AI - Universal Localization Suite v6.0 [PRO ELITE]"
        )
        dialog.setMinimumSize(700, 600)

        # Aplica tema atual sem travar cores fixas
        theme = self._get_theme_colors()
        theme_border = self._get_theme_border_color()
        btn_hover = (
            QColor(theme["button"]).lighter(110).name()
            if self.current_theme != "Preto (Black)"
            else theme["button"]
        )
        dialog.setStyleSheet(
            f"""
            QDialog {{ background-color: {theme['window']}; color: {theme['text']}; }}
            QTextEdit {{
                background-color: {theme['button']};
                color: {theme['text']};
                border: 1px solid {theme_border};
                padding: 15px;
                font-size: 14px;
            }}
            h2 {{ color: {theme['accent']}; }}
            h3 {{ color: #ffcc00; margin-top: 20px; }}
            li {{ margin-bottom: 5px; }}
            QPushButton {{
                background-color: {theme['button']}; color: #b0b0b0; border: none;
                padding: 10px; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
        """
        )

        layout = QVBoxLayout(dialog)

        # TEXTO DO MANUAL TRADUZIDO DINAMICAMENTE (Busca do JSON do idioma atual)
        text_area = QTextEdit()
        text_area.setHtml(self.tr("manual_gfx_body"))
        text_area.setReadOnly(True)
        if self.is_rtl_language():
            text_area.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            text_area.setAlignment(Qt.AlignmentFlag.AlignRight)
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
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

        # TÍTULO TRADUZIDO DINAMICAMENTE
        dialog.setWindowTitle(self.tr("manual_pc_games_title"))
        dialog.setMinimumSize(800, 700)

        # Aplica tema atual sem travar cores fixas
        theme = self._get_theme_colors()
        theme_border = self._get_theme_border_color()
        btn_hover = (
            QColor(theme["button"]).lighter(110).name()
            if self.current_theme != "Preto (Black)"
            else theme["button"]
        )
        dialog.setStyleSheet(
            f"""
            QDialog {{ background-color: {theme['window']}; color: {theme['text']}; }}
            QTextEdit {{
                background-color: {theme['button']};
                color: {theme['text']};
                border: 1px solid {theme_border};
                padding: 15px;
                font-size: 14px;
            }}
            h2 {{ color: {theme['accent']}; }}
            h3 {{ color: #ffcc00; margin-top: 20px; }}
            li {{ margin-bottom: 5px; }}
            QPushButton {{
                background-color: {theme['button']}; color: #b0b0b0; border: none;
                padding: 10px; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
        """
        )

        layout = QVBoxLayout(dialog)

        # TEXTO DO MANUAL TRADUZIDO DINAMICAMENTE
        text_area = QTextEdit()
        text_area.setHtml(self.tr("manual_pc_games_body"))
        text_area.setReadOnly(True)
        if self.is_rtl_language():
            text_area.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            text_area.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(text_area)

        # BOTÃO FECHAR TRADUZIDO DINAMICAMENTE
        btn_close = QPushButton(self.tr("btn_close_manual"))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _create_emoji_text_widget(
        self, emoji: str, text: str, bold: bool = False
    ) -> QWidget:
        """COMMERCIAL GRADE: Create widget with separated emoji and text for consistent sizing."""
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)
        if self.is_rtl_language():
            container.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            h_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Emoji label with fixed large size
        emoji_label = QLabel(emoji)
        emoji_font = QFont("Segoe UI Emoji", 20)  # Fixed large size for emojis
        emoji_label.setFont(emoji_font)
        if self.is_rtl_language():
            emoji_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        h_layout.addWidget(emoji_label)

        # Text label with normal size
        text_label = QLabel(f"<b>{text}</b>" if bold else text)
        text_label.setTextFormat(
            Qt.TextFormat.RichText if bold else Qt.TextFormat.PlainText
        )
        text_font = QFont("Segoe UI", 11)  # Normal text size
        text_label.setFont(text_font)
        text_label.setWordWrap(True)
        if self.is_rtl_language():
            text_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            text_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        h_layout.addWidget(text_label, 1)  # Stretch text label

        return container

    def show_step3_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("help_step3_title"))
        dialog.setMinimumSize(700, 600)
        dialog.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl_language()
            else Qt.LayoutDirection.LeftToRight
        )

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # COMMERCIAL GRADE: Separated emoji/text for consistent sizing
        text_font = QFont("Segoe UI", 11)

        # Objective - Extract emoji from translation
        obj_title_text = self.tr("help_step3_objective_title")
        obj_title = self._create_emoji_text_widget(
            "🎯", obj_title_text.replace("🎯", "").strip(), bold=True
        )
        content_layout.addWidget(obj_title)

        obj_text = QLabel(self.tr("help_step3_objective_text"))
        obj_text.setWordWrap(True)
        obj_text.setFont(text_font)
        self._apply_rtl_label(obj_text)
        content_layout.addWidget(obj_text)
        content_layout.addSpacing(10)

        # Instructions
        inst_title_text = self.tr("help_step3_instructions_title")
        inst_title = self._create_emoji_text_widget(
            "📝", inst_title_text.replace("📝", "").strip(), bold=True
        )
        content_layout.addWidget(inst_title)

        inst_text = QLabel(self.tr("help_step3_instructions_text"))
        inst_text.setWordWrap(True)
        inst_text.setFont(text_font)
        self._apply_rtl_label(inst_text)
        content_layout.addWidget(inst_text)
        content_layout.addSpacing(10)

        # Expectations
        expect_title_text = self.tr("help_step3_expect_title")
        expect_title = self._create_emoji_text_widget(
            "✅", expect_title_text.replace("[OK]", "").strip(), bold=True
        )
        content_layout.addWidget(expect_title)

        expect_text = QLabel(self.tr("help_step3_expect_text"))
        expect_text.setWordWrap(True)
        expect_text.setFont(text_font)
        self._apply_rtl_label(expect_text)
        content_layout.addWidget(expect_text)
        content_layout.addSpacing(10)

        # Auto Mode
        auto_title_text = self.tr("help_step3_automode_title")
        auto_title = self._create_emoji_text_widget(
            "🚀", auto_title_text.replace("[START]", "").strip(), bold=True
        )
        content_layout.addWidget(auto_title)

        auto_text = QLabel(self.tr("help_step3_automode_text"))
        auto_text.setWordWrap(True)
        auto_text.setFont(text_font)
        self._apply_rtl_label(auto_text)
        content_layout.addWidget(auto_text)
        content_layout.addSpacing(10)

        # Estilos de Localização
        style_title_text = self.tr("help_step3_style_title")
        style_title = self._create_emoji_text_widget(
            "🎨", style_title_text.replace("🎨", "").strip(), bold=True
        )
        content_layout.addWidget(style_title)

        style_text = QLabel(self.tr("help_step3_style_text"))
        style_text.setWordWrap(True)
        style_text.setFont(text_font)
        self._apply_rtl_label(style_text)
        content_layout.addWidget(style_text)
        content_layout.addSpacing(10)

        # Gêneros de Jogo
        genre_title_text = self.tr("help_step3_genre_title")
        genre_title = self._create_emoji_text_widget(
            "🎮", genre_title_text.replace("🎮", "").strip(), bold=True
        )
        content_layout.addWidget(genre_title)

        genre_text = QLabel(self.tr("help_step3_genre_text"))
        genre_text.setWordWrap(True)
        genre_text.setFont(text_font)
        self._apply_rtl_label(genre_text)
        content_layout.addWidget(genre_text)
        content_layout.addSpacing(10)

        # Painel de Tradução em Tempo Real
        realtime_title_text = self.tr("help_step3_realtime_title")
        realtime_title = self._create_emoji_text_widget(
            "📺", realtime_title_text.replace("📺", "").strip(), bold=True
        )
        content_layout.addWidget(realtime_title)

        realtime_text = QLabel(self.tr("help_step3_realtime_text"))
        realtime_text.setWordWrap(True)
        realtime_text.setFont(text_font)
        self._apply_rtl_label(realtime_text)
        content_layout.addWidget(realtime_text)
        content_layout.addSpacing(10)

        # Cache de Traduções
        cache_title_text = self.tr("help_step3_cache_title")
        cache_title = self._create_emoji_text_widget(
            "💾", cache_title_text.replace("💾", "").strip(), bold=True
        )
        content_layout.addWidget(cache_title)

        cache_text = QLabel(self.tr("help_step3_cache_text"))
        cache_text.setWordWrap(True)
        cache_text.setFont(text_font)
        self._apply_rtl_label(cache_text)
        content_layout.addWidget(cache_text)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        def _reload_guide():
            dialog.accept()
            QTimer.singleShot(0, self.show_step3_help)

        reload_btn = QPushButton(self.tr("btn_update_guide"))
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.clicked.connect(_reload_guide)

        close_btn = QPushButton(self.tr("btn_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        close_btn.clicked.connect(dialog.accept)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(reload_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

        dialog.exec()

    def load_config(self, silent: bool = False):
        """Load saved configuration from JSON file."""
        if not ProjectConfig.CONFIG_FILE.exists():
            return

        try:
            with open(ProjectConfig.CONFIG_FILE, "r") as f:
                config = json.load(f)

            # Restore theme
            theme_name = config.get("theme", "Preto (Black)")
            if theme_name in ProjectConfig.THEMES:
                self.current_theme = theme_name
                if hasattr(self, "theme_combo"):
                    # Set combo with translated theme name
                    translated_name = self.get_translated_theme_name(theme_name)
                    self.theme_combo.setCurrentText(translated_name)
                self.change_theme(translated_name)

            # Restore UI language
            ui_lang_code = config.get("ui_lang", self.current_ui_lang)
            if ui_lang_code:
                self.current_ui_lang = ui_lang_code
                if hasattr(self, "ui_lang_combo"):
                    self.ui_lang_combo.blockSignals(True)
                    self.ui_lang_combo.setCurrentText(
                        self._get_ui_lang_label(ui_lang_code)
                    )
                    self.ui_lang_combo.blockSignals(False)
            self.apply_layout_direction()

            # Restore font family
            font_name = config.get("font_family", "Padrão (Segoe UI + CJK Fallback)")
            if font_name in ProjectConfig.FONT_FAMILIES:
                self.current_font_family = font_name
                if hasattr(self, "font_combo"):
                    self.font_combo.setCurrentText(font_name)
                self.change_font_family(font_name)

            # Restore workers and timeout
            if hasattr(self, "workers_spin"):
                self.workers_spin.setValue(config.get("workers", 4))
            if hasattr(self, "timeout_spin"):
                self.timeout_spin.setValue(config.get("timeout", 30))

            # Restore onboarding state
            self.onboarding_shown = bool(config.get("onboarding_shown", False))

            # Restore last used folders
            self.last_rom_dir = config.get("last_rom_dir", self.last_rom_dir)
            self.last_text_dir = config.get("last_text_dir", self.last_text_dir)

            # Restore max extraction mode
            self.max_extraction_mode = bool(config.get("max_extraction_mode", False))
            if hasattr(self, "max_extract_cb"):
                self.max_extract_cb.setChecked(self.max_extraction_mode)
            if self.max_extraction_locked:
                self.max_extraction_mode = True
                if hasattr(self, "max_extract_cb"):
                    self.max_extract_cb.blockSignals(True)
                    self.max_extract_cb.setChecked(True)
                    self.max_extract_cb.setEnabled(False)
                    self.max_extract_cb.setToolTip(
                        self.tr("tooltip_max_extraction_locked")
                    )
                    self.max_extract_cb.blockSignals(False)

            # Restore beginner mode
            self.beginner_mode = bool(config.get("beginner_mode", True))
            if hasattr(self, "beginner_mode_cb"):
                self.beginner_mode_cb.setChecked(True)
                self.beginner_mode_cb.setEnabled(False)

            # Developer mode / auto graphics
            self.developer_mode = bool(config.get("developer_mode", False))
            self.auto_graphics_pipeline = bool(config.get("auto_graphics_pipeline", True))
            if hasattr(self, "tabs"):
                try:
                    self.tabs.setTabVisible(1, bool(self.developer_mode))
                except Exception:
                    self.tabs.setTabEnabled(1, bool(self.developer_mode))

            # Restore window geometry/state (profissional)
            geom_b64 = config.get("window_geometry")
            if geom_b64:
                try:
                    geom = QByteArray.fromBase64(geom_b64.encode("utf-8"))
                    self.restoreGeometry(geom)
                except Exception:
                    pass

            if config.get("window_maximized"):
                self.showMaximized()
            else:
                self._ensure_window_visible()

            # Restore log panel visibility
            log_visible = config.get("log_visible", True)
            if hasattr(self, "log_group") and hasattr(self, "log_toggle_btn"):
                self.log_group.setVisible(bool(log_visible))
                self.log_toggle_btn.setText(
                    self.tr("log_hide") if log_visible else self.tr("log_show")
                )

            # CRITICAL FIX: Refresh UI labels after restoring language
            self.refresh_ui_labels()

            # Restore last tab
            if hasattr(self, "tabs"):
                last_tab = config.get("last_tab_index")
                if isinstance(last_tab, int) and 0 <= last_tab < self.tabs.count():
                    self.tabs.setCurrentIndex(last_tab)

            self._apply_beginner_mode()
            self._update_action_states()

            if not silent:
                self.log("Configuração carregada com sucesso.")

        except Exception as e:
            self.log(f"Falha ao carregar configuração: {_sanitize_error(e)}")

    def save_config(self):
        """Save current configuration to JSON file."""

        def _obfuscate_key(key: str) -> str:
            if not key:
                return ""
            return base64.b64encode(key.encode("utf-8")).decode("utf-8")

        config = {
            "theme": self.current_theme,
            "ui_lang": self.current_ui_lang,
            "font_family": self.current_font_family,
            "api_key_obfuscated": _obfuscate_key(self.api_key_edit.text()),
            "workers": self.workers_spin.value(),
            "timeout": self.timeout_spin.value(),
            "last_saved": datetime.now().isoformat(),
            "onboarding_shown": bool(getattr(self, "onboarding_shown", False)),
            "last_rom_dir": getattr(self, "last_rom_dir", ""),
            "last_text_dir": getattr(self, "last_text_dir", ""),
            "max_extraction_mode": bool(getattr(self, "max_extraction_mode", False)),
            "beginner_mode": bool(getattr(self, "beginner_mode", False)),
            "developer_mode": bool(getattr(self, "developer_mode", False)),
            "auto_graphics_pipeline": bool(getattr(self, "auto_graphics_pipeline", False)),
        }
        try:
            config["window_geometry"] = (
                self.saveGeometry().toBase64().data().decode("utf-8")
            )
            config["window_maximized"] = self.isMaximized()
            if hasattr(self, "log_group"):
                config["log_visible"] = self.log_group.isVisible()
            if hasattr(self, "tabs"):
                config["last_tab_index"] = self.tabs.currentIndex()
        except Exception:
            pass
        try:
            with open(ProjectConfig.CONFIG_FILE, "w") as f:
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
            self.engine_detection_thread = EngineDetectionWorkerTier1(
                self.original_rom_path
            )
            # Conecta o sinal de progresso específico do Tier1
            self.engine_detection_thread.progress_signal.connect(
                self.on_engine_detection_progress
            )
        else:
            self.engine_detection_thread = EngineDetectionWorker(self.original_rom_path)

        # USA O MÉTODO COMPLETO que já existe e funciona perfeitamente
        self.engine_detection_thread.detection_complete.connect(
            self.on_engine_detection_complete
        )

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
    os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
