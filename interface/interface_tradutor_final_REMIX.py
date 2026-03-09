# -*- coding: utf-8 -*-
"""
================================================================================
TRADUTOR UNIVERSAL DE ROMs v5.3 - REMIX VISUAL
Desenvolvido por: Celso (Programador Solo)
Arquitetura: Multi-plataforma + Multi-idioma + Auto-detecção
================================================================================
REMIX EDITION:
✓ Visual Sagrado do Backup V5.3 (Cores, Fontes, Layout)
✓ Estrutura Moderna com gui_tabs (ExtractionTab, ReinsertionTab, GraphicLabTab)
✓ Compatibilidade com hasattr() para widgets opcionais
✓ Layout: 70% Abas + 30% Log (do backup)
✓ Botões: Verde #4CAF50 / Laranja #FF9800 / Preto #000000
================================================================================
"""

import sys
import os
import json
import subprocess
import re
import shutil
import traceback
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# ================== IMPORTS DAS NOVAS ABAS (gui_tabs) ==================
try:
    from gui_tabs.extraction_tab import ExtractionTab
    from gui_tabs.reinsertion_tab import ReinsertionTab
    from gui_tabs.graphic_lab import GraphicLabTab
    print("✓ gui_tabs importados com sucesso")
except ImportError as e:
    print(f"✗ Erro ao importar gui_tabs: {e}")
    # Fallback classes
    class ExtractionTab:
        def __init__(self, parent=None):
            pass
        def set_rom_path(self, path):
            pass
        def retranslate(self):
            pass
    class ReinsertionTab:
        def __init__(self, parent=None):
            pass
        def set_rom_path(self, path):
            pass
        def retranslate(self):
            pass
    class GraphicLabTab:
        def __init__(self, parent=None):
            pass
        def set_rom_path(self, path):
            pass
        def retranslate(self):
            pass

# ================== CONFIGURAÇÃO DO SYS.PATH ==================
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# ================== IMPORTS CORE ==================
try:
    from core.gemini_translator import GeminiTranslator
    print("✓ GeminiTranslator importado")
except ImportError as e:
    print(f"✗ Erro ao importar GeminiTranslator: {e}")
    class GeminiTranslator:
        def __init__(self):
            self.name = "GeminiTranslator (placeholder)"
        def translate(self, text, **kwargs):
            return f"[TRADUÇÃO SIMULADA: {text[:50]}...]"

try:
    from core.engine_detector import EngineDetector, detect_game_engine
    print("✓ EngineDetector importado")
except ImportError as e:
    print(f"✗ Erro ao importar EngineDetector: {e}")
    def detect_game_engine(file_path):
        return {'type': 'UNKNOWN', 'platform': 'Unknown', 'engine': 'Unknown', 'notes': 'Engine detector não disponível'}

try:
    from core.security_manager import SecurityManager
    print("✓ SecurityManager importado")
except ImportError as e:
    print(f"✗ Erro ao importar SecurityManager: {e}")
    SecurityManager = None

# ================== IMPORTS PyQt6 ==================
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

# ================== WORKERS (THREADS) ==================

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
            self.finished.emit(False, f"Exception: {str(e)}")

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
    """Worker dedicado para otimização de dados em thread separada."""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, input_file: str):
        super().__init__()
        self.input_file = input_file
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.status_signal.emit("Processando...")
            self.progress_signal.emit(50)

            # Simulação de processamento
            import time
            time.sleep(1)

            self.progress_signal.emit(100)
            self.finished_signal.emit(self.input_file)
        except Exception as e:
            self.error_signal.emit(str(e))


# ================== PROJECT CONFIG ==================

class ProjectConfig:
    """Configuração do projeto"""
    BASE_DIR = Path(__file__).parent
    ROMS_DIR = BASE_DIR.parent / "ROMs"
    SCRIPTS_DIR = BASE_DIR.parent / "Scripts principais"
    CONFIG_FILE = BASE_DIR / "translator_config.json"
    I18N_DIR = BASE_DIR.parent / "i18n"

    PLATFORMS = {
        "Super Nintendo (SNES)": {"code": "snes", "ready": True, "label": "platform_snes"},
        "PC Games (Windows)": {"code": "pc", "ready": True, "label": "platform_pc"},
        "PlayStation 1 (PS1)": {"code": "ps1", "ready": False, "label": "platform_ps1"},
        "Nintendo (NES)": {"code": "nes", "ready": False, "label": "platform_nes"},
        "Nintendo 64 (N64)": {"code": "n64", "ready": False, "label": "platform_n64"},
        "Game Boy Advance (GBA)": {"code": "gba", "ready": False, "label": "platform_gba"},
    }

    UI_LANGUAGES = {
        "🇧🇷 Português (Brasil)": "pt",
        "🇺🇸 English (US)": "en",
        "🇪🇸 Español (España)": "es",
        "🇫🇷 Français (France)": "fr",
        "🇩🇪 Deutsch (Deutschland)": "de",
        "🇮🇹 Italiano (Italia)": "it",
        "🇯🇵 日本語 (Japanese)": "ja",
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
        "Francês (Français)": "fr",
        "Alemão (Deutsch)": "de",
        "Italiano (Italiano)": "it",
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

    THEME_TRANSLATION_KEYS = {
        "Preto (Black)": "theme_black",
        "Cinza (Gray)": "theme_gray",
        "Branco (White)": "theme_white"
    }

    @classmethod
    def ensure_directories(cls):
        cls.ROMS_DIR.mkdir(exist_ok=True, parents=True)
        cls.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        os.makedirs("projects", exist_ok=True)
        os.makedirs("cache", exist_ok=True)

    _translations_cache = {}

    @classmethod
    def load_translations(cls, lang_code: str) -> Dict:
        """Load translations from JSON file with caching. Fallback hierarchy: requested lang → en → empty dict"""
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
                print(f"⚠️ Failed to load {lang_code}.json: {e}")

        # Fallback to English if not 'en' itself
        if lang_code != "en":
            return cls.load_translations("en")

        return {}


# ================== THEME MANAGER ==================

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


# ================== MAIN WINDOW (REMIX EDITION) ==================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Variáveis de estado
        self.original_rom_path: Optional[str] = None
        self.extracted_file: Optional[str] = None
        self.optimized_file: Optional[str] = None
        self.translated_file: Optional[str] = None

        self.current_theme = "Preto (Black)"
        self.current_ui_lang = "pt"
        self.current_font_family = "Padrão (Segoe UI + CJK Fallback)"

        # Referências para workers
        self.extract_thread: Optional[ProcessThread] = None
        self.optimize_thread: Optional[OptimizationWorker] = None

        # Inicializar UI
        self.init_ui()
        self.load_config()
        ProjectConfig.ensure_directories()

        # Atualizar labels (com verificação de atributos)
        if hasattr(self, 'tabs'):
            self.refresh_ui_labels()

    def tr(self, key: str) -> str:
        """i18n translation with triple fallback"""
        # Level 1: Current language
        current_translations = ProjectConfig.load_translations(self.current_ui_lang)
        translation = current_translations.get(key)

        # Level 2: Fallback to English
        if translation is None:
            en_translations = ProjectConfig.load_translations("en")
            translation = en_translations.get(key)

        # Level 3: Visual debug fallback
        if translation is None:
            return f"[{key}]"

        return translation

    def get_translated_theme_name(self, internal_key: str) -> str:
        """Convert internal theme key to translated theme name."""
        translation_key = ProjectConfig.THEME_TRANSLATION_KEYS.get(internal_key)
        if translation_key:
            return self.tr(translation_key)
        return internal_key

    def get_internal_theme_key(self, translated_name: str) -> str:
        """Convert translated theme name back to internal theme key."""
        for internal_key, translation_key in ProjectConfig.THEME_TRANSLATION_KEYS.items():
            if self.tr(translation_key) == translated_name:
                return internal_key
        return translated_name

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
        return internal_key

    def get_internal_source_language_key(self, translated_name: str) -> str:
        """Convert translated source language name back to internal key."""
        if translated_name == self.tr("auto_detect"):
            return "AUTO-DETECTAR"
        return translated_name

    def get_all_translated_source_languages(self) -> list:
        """Get all source language names with AUTO-DETECTAR translated."""
        translated_names = []
        for internal_key in ProjectConfig.SOURCE_LANGUAGES.keys():
            translated_names.append(self.get_translated_source_language_name(internal_key))
        return translated_names

    def update_window_title(self):
        """Atualiza título da janela"""
        self.setWindowTitle("NeuroROM AI - Universal Localization Suite v5.3 REMIX")

    def init_ui(self):
        """
        ═══════════════════════════════════════════════════════════
        REMIX UI - Visual Sagrado + Estrutura Moderna + Abas Completas
        ═══════════════════════════════════════════════════════════
        """
        # VISUAL SAGRADO: Tamanho da janela
        self.setWindowTitle("NeuroROM AI - Universal Localization Suite v5.3 REMIX")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ═══════════════════════════════════════════════════════════
        # PAINEL ESQUERDO: ABAS (70% - 3/5 do espaço)
        # ═══════════════════════════════════════════════════════════
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.tabs = QTabWidget()

        # ABA 1: EXTRAÇÃO (do BACKUP - preenchida com widgets)
        self.tabs.addTab(self.create_extraction_tab(), self.tr("tab1"))

        # ABA 2: TRADUÇÃO (do BACKUP - preenchida com widgets)
        self.tabs.addTab(self.create_translation_tab(), self.tr("tab2"))

        # ABA 3: REINSERÇÃO (do BACKUP - preenchida com widgets)
        self.tabs.addTab(self.create_reinsertion_tab(), self.tr("tab3"))

        # ABA 4: GRÁFICOS (MANTIDO DO REMIX - Perfeito!)
        if GraphicLabTab:
            self.graphics_lab_tab = GraphicLabTab(parent=self)
            self.tabs.addTab(self.graphics_lab_tab, self.tr("tab5"))

        # ABA 5: CONFIGURAÇÕES (do BACKUP - com sistema de temas)
        self.tabs.addTab(self.create_settings_tab(), self.tr("tab4"))

        left_layout.addWidget(self.tabs)
        main_layout.addWidget(left_panel, 3)

        # ═══════════════════════════════════════════════════════════
        # PAINEL DIREITO: LOG (30% - 2/5 do espaço)
        # ═══════════════════════════════════════════════════════════
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        log_group = QGroupBox(self.tr("log"))
        log_group.setObjectName("log_group")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        # VISUAL SAGRADO: Botão Reiniciar (Verde)
        restart_btn = QPushButton(self.tr("restart"))
        restart_btn.setObjectName("restart_btn")
        restart_btn.setMinimumHeight(40)
        restart_btn.setStyleSheet(
            "QPushButton{background-color:#4CAF50;color:white;font-size:12pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#45a049;}"
        )
        restart_btn.clicked.connect(self.restart_application)
        right_layout.addWidget(restart_btn)

        # VISUAL SAGRADO: Botão Sair (Preto)
        exit_btn = QPushButton(self.tr("exit"))
        exit_btn.setObjectName("exit_btn")
        exit_btn.setMinimumHeight(40)
        exit_btn.setStyleSheet(
            "QPushButton{background-color:#000000;color:#FFFFFF;font-size:12pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#222222;}"
        )
        exit_btn.clicked.connect(self.close)
        right_layout.addWidget(exit_btn)

        # VISUAL SAGRADO: Copyright Footer
        copyright_label = QLabel("Developed by Celso - Programador Solo | © 2025 All Rights Reserved")
        copyright_label.setObjectName("copyright_label")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color:#888;font-size:9pt;font-weight:bold;")
        right_layout.addWidget(copyright_label)

        main_layout.addWidget(right_panel, 2)

        self.statusBar().showMessage("NeuroROM AI Ready - REMIX Edition")
        self.log("Sistema v5.3 REMIX iniciado - Visual Sagrado Aplicado")

    def create_extraction_tab(self) -> QWidget:
        """ABA 1: EXTRAÇÃO - widgets do BACKUP sem estilos hardcoded"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        platform_group = QGroupBox(self.tr("platform"))
        platform_group.setObjectName("platform_group")
        platform_layout = QHBoxLayout()
        self.platform_combo = QComboBox()

        for platform_name, data in ProjectConfig.PLATFORMS.items():
            platform_code = data.get("code", "")
            self.platform_combo.addItem(platform_name, platform_code)

        platform_layout.addWidget(self.platform_combo)
        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        rom_group = QGroupBox(self.tr("rom_file"))
        rom_group.setObjectName("rom_file_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()
        self.rom_path_label = QLabel(self.tr("no_rom"))
        self.rom_path_label.setObjectName("rom_path_label")
        rom_select_layout.addWidget(self.rom_path_label)
        self.select_rom_btn = QPushButton(self.tr("select_rom"))
        self.select_rom_btn.setObjectName("select_rom_btn")
        self.select_rom_btn.clicked.connect(self.select_rom)
        rom_select_layout.addWidget(self.select_rom_btn)
        rom_layout.addLayout(rom_select_layout)
        rom_group.setLayout(rom_layout)
        layout.addWidget(rom_group)

        self.extract_btn = QPushButton(self.tr("extract_texts"))
        self.extract_btn.setObjectName("extract_btn")
        self.extract_btn.setMinimumHeight(50)
        self.extract_btn.setStyleSheet(
            "QPushButton{background-color:#4CAF50;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#45a049;}"
            "QPushButton:disabled{background-color:#cccccc;color:#666666;}"
        )
        self.extract_btn.clicked.connect(self.extract_texts)
        layout.addWidget(self.extract_btn)

        self.optimize_btn = QPushButton(self.tr("optimize_data"))
        self.optimize_btn.setObjectName("optimize_btn")
        self.optimize_btn.setMinimumHeight(50)
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.clicked.connect(self.optimize_data)
        self.optimize_btn.setStyleSheet(
            "QPushButton{background-color:#FF9800;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#e68900;}"
            "QPushButton:disabled{background-color:#cccccc;}"
        )
        layout.addWidget(self.optimize_btn)

        extract_progress_group = QGroupBox(self.tr("extraction_progress"))
        extract_progress_group.setObjectName("extract_progress_group")
        extract_progress_layout = QVBoxLayout()
        self.extract_progress_bar = QProgressBar()
        self.extract_progress_bar.setFormat("%p%")
        extract_progress_layout.addWidget(self.extract_progress_bar)
        self.extract_status_label = QLabel(self.tr("waiting"))
        self.extract_status_label.setObjectName("extract_status_label")
        self.extract_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        extract_progress_layout.addWidget(self.extract_status_label)
        extract_progress_group.setLayout(extract_progress_layout)
        layout.addWidget(extract_progress_group)

        optimize_progress_group = QGroupBox(self.tr("optimization_progress"))
        optimize_progress_group.setObjectName("optimize_progress_group")
        optimize_progress_layout = QVBoxLayout()
        self.optimize_progress_bar = QProgressBar()
        self.optimize_progress_bar.setFormat("%p%")
        optimize_progress_layout.addWidget(self.optimize_progress_bar)
        self.optimize_status_label = QLabel(self.tr("waiting"))
        self.optimize_status_label.setObjectName("optimize_status_label")
        self.optimize_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        optimize_progress_layout.addWidget(self.optimize_status_label)
        optimize_progress_group.setLayout(optimize_progress_layout)
        layout.addWidget(optimize_progress_group)

        layout.addStretch()
        return widget

    def create_translation_tab(self) -> QWidget:
        """ABA 2: TRADUÇÃO - widgets do BACKUP sem estilos hardcoded"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        file_group = QGroupBox(self.tr("file_to_translate"))
        file_group.setObjectName("file_to_translate_group")
        file_layout = QHBoxLayout()

        self.trans_file_label = QLabel(self.tr("no_file"))
        self.trans_file_label.setObjectName("trans_file_label")
        self.trans_file_label.setStyleSheet("color: #888;")
        file_layout.addWidget(self.trans_file_label)

        self.sel_file_btn = QPushButton(self.tr("select_file"))
        self.sel_file_btn.setObjectName("sel_file_btn")
        self.sel_file_btn.clicked.connect(self.select_translation_input_file)
        file_layout.addWidget(self.sel_file_btn)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        lang_config_group = QGroupBox(self.tr("language_config"))
        lang_config_group.setObjectName("lang_config_group")
        lang_config_layout = QGridLayout()
        source_lang_label = QLabel(self.tr("source_language"))
        source_lang_label.setObjectName("source_lang_label")
        lang_config_layout.addWidget(source_lang_label, 0, 0)
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(self.get_all_translated_source_languages())
        lang_config_layout.addWidget(self.source_lang_combo, 0, 1)
        target_lang_label = QLabel(self.tr("target_language"))
        target_lang_label.setObjectName("target_lang_label")
        lang_config_layout.addWidget(target_lang_label, 1, 0)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
        lang_config_layout.addWidget(self.target_lang_combo, 1, 1)
        lang_config_group.setLayout(lang_config_layout)
        layout.addWidget(lang_config_group)

        mode_group = QGroupBox(self.tr("translation_mode"))
        mode_group.setObjectName("mode_group")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "🤖 Auto (Gemini → Ollama)",
            "⚡ Online Gemini (Google API)",
            "🚀 Offline Rápido (Llama 3.2) [RECOMENDADO]",
            "🔥 Offline Alta Qualidade (Mistral 7B) [Requer 8GB+ VRAM]",
            "🌐 Online DeepL (API)"
        ])
        self.mode_combo.setCurrentText("🚀 Offline Rápido (Llama 3.2) [RECOMENDADO]")
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.api_group = QGroupBox(self.tr("api_config"))
        self.api_group.setObjectName("api_group")
        self.api_group.setVisible(True)
        api_layout = QGridLayout()
        api_key_label = QLabel(self.tr("api_key"))
        api_key_label.setObjectName("api_key_label")
        api_layout.addWidget(api_key_label, 0, 0)

        api_container = QWidget()
        api_container_layout = QHBoxLayout(api_container)
        api_container_layout.setContentsMargins(0, 0, 0, 0)
        api_container_layout.setSpacing(5)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.eye_btn = QPushButton("👁️")
        self.eye_btn.setFixedWidth(40)
        self.eye_btn.setCheckable(True)
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self.toggle_api_visibility)

        api_container_layout.addWidget(self.api_key_edit)
        api_container_layout.addWidget(self.eye_btn)

        api_layout.addWidget(api_container, 0, 1)
        workers_label = QLabel(self.tr("workers"))
        workers_label.setObjectName("workers_label")
        api_layout.addWidget(workers_label, 1, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setMinimum(1)
        self.workers_spin.setMaximum(10)
        self.workers_spin.setValue(3)
        api_layout.addWidget(self.workers_spin, 1, 1)
        timeout_label = QLabel(self.tr("timeout"))
        timeout_label.setObjectName("timeout_label")
        api_layout.addWidget(timeout_label, 2, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimum(30)
        self.timeout_spin.setMaximum(300)
        self.timeout_spin.setValue(120)
        api_layout.addWidget(self.timeout_spin, 2, 1)
        cache_check = QCheckBox(self.tr("use_cache"))
        cache_check.setObjectName("cache_check")
        cache_check.setChecked(True)
        api_layout.addWidget(cache_check, 3, 0, 1, 2)
        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)

        translation_progress_group = QGroupBox(self.tr("translation_progress"))
        translation_progress_group.setObjectName("translation_progress_group")
        translation_progress_layout = QVBoxLayout()
        self.translation_progress_bar = QProgressBar()
        self.translation_progress_bar.setFormat("%p%")
        translation_progress_layout.addWidget(self.translation_progress_bar)
        self.translation_status_label = QLabel(self.tr("waiting"))
        self.translation_status_label.setObjectName("translation_status_label")
        self.translation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        translation_progress_layout.addWidget(self.translation_status_label)
        translation_progress_group.setLayout(translation_progress_layout)
        layout.addWidget(translation_progress_group)

        self.translate_btn = QPushButton(self.tr("translate_ai"))
        self.translate_btn.setObjectName("translate_btn")
        self.translate_btn.setMinimumHeight(50)
        self.translate_btn.setStyleSheet(
            "QPushButton{background-color:#2196F3;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#0b7dda;}"
        )
        self.translate_btn.clicked.connect(self.translate_texts)
        layout.addWidget(self.translate_btn)

        self.stop_translation_btn = QPushButton(self.tr("stop_translation"))
        self.stop_translation_btn.setObjectName("stop_translation_btn")
        self.stop_translation_btn.setMinimumHeight(50)
        self.stop_translation_btn.setStyleSheet(
            "QPushButton{background-color:#000000;color:#FFFFFF;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#222222;}"
        )
        self.stop_translation_btn.setEnabled(False)
        layout.addWidget(self.stop_translation_btn)

        layout.addStretch()
        return widget

    def create_reinsertion_tab(self) -> QWidget:
        """ABA 3: REINSERÇÃO - widgets do BACKUP sem estilos hardcoded"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        rom_group = QGroupBox(self.tr("original_rom"))
        rom_group.setObjectName("reinsert_rom_group")
        rom_layout = QVBoxLayout()
        rom_select_layout = QHBoxLayout()
        self.reinsert_rom_label = QLabel(self.tr("no_rom"))
        self.reinsert_rom_label.setObjectName("reinsert_rom_label")
        rom_select_layout.addWidget(self.reinsert_rom_label)
        select_reinsert_rom_btn = QPushButton(self.tr("select_rom"))
        select_reinsert_rom_btn.setObjectName("select_reinsert_rom_btn")
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
        trans_select_layout.addWidget(self.translated_file_label)
        select_translated_btn = QPushButton(self.tr("select_file"))
        select_translated_btn.setObjectName("select_translated_btn")
        select_translated_btn.clicked.connect(self.select_translated_file)
        trans_select_layout.addWidget(select_translated_btn)
        trans_layout.addLayout(trans_select_layout)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        output_group = QGroupBox(self.tr("output_rom"))
        output_group.setObjectName("output_rom_group")
        output_layout = QVBoxLayout()
        self.output_rom_edit = QLineEdit()
        self.output_rom_edit.setPlaceholderText("Ex: jogo_PTBR.bin")
        output_layout.addWidget(self.output_rom_edit)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        reinsertion_progress_group = QGroupBox(self.tr("reinsertion_progress"))
        reinsertion_progress_group.setObjectName("reinsertion_progress_group")
        reinsertion_progress_layout = QVBoxLayout()
        self.reinsertion_progress_bar = QProgressBar()
        self.reinsertion_progress_bar.setFormat("%p%")
        reinsertion_progress_layout.addWidget(self.reinsertion_progress_bar)
        self.reinsertion_status_label = QLabel(self.tr("waiting"))
        self.reinsertion_status_label.setObjectName("reinsertion_status_label")
        self.reinsertion_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reinsertion_progress_layout.addWidget(self.reinsertion_status_label)
        reinsertion_progress_group.setLayout(reinsertion_progress_layout)
        layout.addWidget(reinsertion_progress_group)

        self.reinsert_btn = QPushButton(self.tr("reinsert"))
        self.reinsert_btn.setObjectName("reinsert_btn")
        self.reinsert_btn.setMinimumHeight(50)
        self.reinsert_btn.setStyleSheet(
            "QPushButton{background-color:#FF9800;color:white;font-size:14pt;"
            "font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background-color:#e68900;}"
        )
        self.reinsert_btn.clicked.connect(self.reinsert)
        layout.addWidget(self.reinsert_btn)

        layout.addStretch()
        return widget

    def create_settings_tab(self) -> QWidget:
        """ABA 5: CONFIGURAÇÕES - com sistema de temas do BACKUP"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ui_lang_group = QGroupBox(self.tr("ui_language"))
        ui_lang_group.setObjectName("ui_lang_group")
        ui_lang_layout = QHBoxLayout()
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setMaxVisibleItems(15)
        self.ui_lang_combo.addItems(ProjectConfig.UI_LANGUAGES.keys())
        self.ui_lang_combo.currentTextChanged.connect(self.change_ui_language)
        ui_lang_layout.addWidget(self.ui_lang_combo)
        ui_lang_group.setLayout(ui_lang_layout)
        layout.addWidget(ui_lang_group)

        theme_group = QGroupBox(self.tr("theme"))
        theme_group.setObjectName("theme_group")
        theme_layout = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.get_all_translated_theme_names())
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
        self.font_combo.addItems(ProjectConfig.FONT_FAMILIES.keys())
        self.font_combo.setCurrentText(self.current_font_family)
        self.font_combo.currentTextChanged.connect(self.change_font_family)
        font_layout.addWidget(self.font_combo)
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        layout.addStretch()
        version_label = QLabel("Versão do Sistema: v5.3 REMIX")
        version_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        return widget

    def refresh_ui_labels(self):
        """Atualiza labels da interface (com verificações)"""
        try:
            self.update_window_title()

            # Atualizar tabs se existirem
            if hasattr(self, 'tabs') and self.tabs:
                if self.tabs.count() > 0:
                    self.tabs.setTabText(0, self.tr("tab1"))
                if self.tabs.count() > 1:
                    self.tabs.setTabText(1, self.tr("tab2"))
                if self.tabs.count() > 2:
                    self.tabs.setTabText(2, self.tr("tab3"))
                if self.tabs.count() > 3:
                    self.tabs.setTabText(3, self.tr("tab5"))
                if self.tabs.count() > 4:
                    self.tabs.setTabText(4, self.tr("tab4"))

            # Atualizar abas personalizadas
            if hasattr(self, 'graphics_lab_tab') and hasattr(self.graphics_lab_tab, 'retranslate'):
                self.graphics_lab_tab.retranslate()

            # Update theme combo with translated names
            if hasattr(self, 'theme_combo'):
                self.theme_combo.blockSignals(True)
                self.theme_combo.clear()
                self.theme_combo.addItems(self.get_all_translated_theme_names())
                current_translated = self.get_translated_theme_name(self.current_theme)
                self.theme_combo.setCurrentText(current_translated)
                self.theme_combo.blockSignals(False)

            if hasattr(self, 'log_text'):
                self.log("UI atualizada")
        except Exception as e:
            if hasattr(self, 'log_text'):
                self.log(f"Erro refresh_ui_labels: {str(e)}")

    # ========== MÉTODOS DE CONFIGURAÇÃO ==========

    def change_ui_language(self, lang_name: str):
        """Muda o idioma da interface"""
        lang_code = ProjectConfig.UI_LANGUAGES.get(lang_name)
        if lang_code:
            self.current_ui_lang = lang_code
            self.refresh_ui_labels()
            self.save_config()
            self.log(f"Idioma alterado para: {lang_name}")

    def change_theme(self, theme_name: str):
        """Muda o tema visual"""
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key
        ThemeManager.apply(QApplication.instance(), internal_key)
        self.save_config()
        self.log(f"Tema alterado para: {internal_key}")

    def change_font_family(self, font_name: str):
        """Muda a fonte da interface"""
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
        """Alterna visibilidade da API key"""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.eye_btn.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.eye_btn.setText("👁️")

    # ========== MÉTODOS DE SELEÇÃO DE ARQUIVOS ==========

    def select_rom(self):
        """Seleciona ROM original"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), str(ProjectConfig.ROMS_DIR),
            "ROMs (*.bin *.iso *.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds);;All (*.*)"
        )
        if file_path:
            self.original_rom_path = file_path
            self.rom_path_label.setText(Path(file_path).name)
            self.rom_path_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            if hasattr(self, 'reinsert_rom_label'):
                self.reinsert_rom_label.setText(Path(file_path).name)
                self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"ROM selecionada: {Path(file_path).name}")

    def select_translation_input_file(self):
        """Seleciona arquivo para traduzir"""
        initial_dir = str(ProjectConfig.ROMS_DIR)
        if self.original_rom_path and os.path.exists(os.path.dirname(self.original_rom_path)):
            initial_dir = os.path.dirname(self.original_rom_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), initial_dir,
            "Text Files (*.txt *.optimized.txt *.translated.txt);;All Files (*.*)"
        )

        if file_path:
            self.optimized_file = file_path
            self.trans_file_label.setText(os.path.basename(file_path))
            self.trans_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.log(f"Arquivo carregado: {os.path.basename(file_path)}")

    def select_rom_for_reinsertion(self):
        """Seleciona ROM para reinserção"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_rom"), str(ProjectConfig.ROMS_DIR),
            "ROMs (*.bin *.iso *.smc *.sfc *.z64 *.n64 *.gba *.gb *.gbc *.nds);;All (*.*)"
        )
        if file_path:
            self.original_rom_path = file_path
            self.reinsert_rom_label.setText(Path(file_path).name)
            self.reinsert_rom_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            if hasattr(self, 'rom_path_label'):
                self.rom_path_label.setText(Path(file_path).name)
                self.rom_path_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"ROM para reinserção: {Path(file_path).name}")

    def select_translated_file(self):
        """Seleciona arquivo traduzido"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("select_file"), str(ProjectConfig.ROMS_DIR),
            "Text Files (*.txt *.translated.txt);;All Files (*.*)"
        )
        if file_path:
            self.translated_file = file_path
            self.translated_file_label.setText(Path(file_path).name)
            self.translated_file_label.setStyleSheet("color:#4CAF50;font-weight:bold;")
            self.log(f"Arquivo traduzido: {Path(file_path).name}")

    # ========== MÉTODOS DE PROCESSAMENTO ==========

    def extract_texts(self):
        """Extrai textos da ROM (placeholder)"""
        if not self.original_rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma ROM primeiro!")
            return
        self.log("Iniciando extração de textos...")
        self.extract_status_label.setText("Processando...")
        self.extract_progress_bar.setValue(0)
        # TODO: Implementar lógica de extração

    def optimize_data(self):
        """Otimiza dados extraídos (placeholder)"""
        self.log("Iniciando otimização de dados...")
        self.optimize_status_label.setText("Processando...")
        self.optimize_progress_bar.setValue(0)
        # TODO: Implementar lógica de otimização

    def translate_texts(self):
        """Traduz textos com IA (placeholder)"""
        if not self.optimized_file:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo para traduzir!")
            return
        self.log("Iniciando tradução com IA...")
        self.translation_status_label.setText("Processando...")
        self.translation_progress_bar.setValue(0)
        # TODO: Implementar lógica de tradução

    def reinsert(self):
        """Reinsere tradução na ROM (placeholder)"""
        if not self.original_rom_path or not self.translated_file:
            QMessageBox.warning(self, "Aviso", "Selecione ROM e arquivo traduzido!")
            return
        self.log("Iniciando reinserção...")
        self.reinsertion_status_label.setText("Processando...")
        self.reinsertion_progress_bar.setValue(0)
        # TODO: Implementar lógica de reinserção

    # ========== MÉTODOS DE CONFIGURAÇÃO DE ESTADO ==========

    def load_config(self):
        """Carrega configuração do arquivo JSON"""
        try:
            config_file = ProjectConfig.CONFIG_FILE if hasattr(ProjectConfig, 'CONFIG_FILE') else Path("translator_config.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                    # Restaurar tema
                    if 'theme' in config:
                        self.current_theme = config['theme']
                        translated_name = self.get_translated_theme_name(self.current_theme)
                        if hasattr(self, 'theme_combo'):
                            self.theme_combo.setCurrentText(translated_name)
                        ThemeManager.apply(QApplication.instance(), self.current_theme)

                    # Restaurar idioma
                    if 'ui_lang' in config:
                        self.current_ui_lang = config['ui_lang']
                        for name, code in ProjectConfig.UI_LANGUAGES.items():
                            if code == self.current_ui_lang:
                                if hasattr(self, 'ui_lang_combo'):
                                    self.ui_lang_combo.setCurrentText(name)
                                break

                    # Restaurar fonte
                    if 'font_family' in config:
                        self.current_font_family = config['font_family']
                        if hasattr(self, 'font_combo'):
                            self.font_combo.setCurrentText(self.current_font_family)
                        self.change_font_family(self.current_font_family)

                    # Restaurar API key (se tiver)
                    if 'api_key_obfuscated' in config and hasattr(self, 'api_key_edit'):
                        try:
                            decoded_key = base64.b64decode(config['api_key_obfuscated']).decode('utf-8')
                            self.api_key_edit.setText(decoded_key)
                        except:
                            pass

                    # Restaurar workers e timeout
                    if hasattr(self, 'workers_spin') and 'workers' in config:
                        self.workers_spin.setValue(config.get('workers', 3))
                    if hasattr(self, 'timeout_spin') and 'timeout' in config:
                        self.timeout_spin.setValue(config.get('timeout', 120))

                    self.log("Configuração carregada")
        except Exception as e:
            self.log(f"Erro ao carregar config: {e}")

    def save_config(self):
        """Salva configuração no arquivo JSON"""
        try:
            config = {
                'theme': self.current_theme,
                'ui_lang': self.current_ui_lang,
                'font_family': self.current_font_family,
                'last_saved': datetime.now().isoformat()
            }

            # Salvar API key ofuscada (se existir)
            if hasattr(self, 'api_key_edit') and self.api_key_edit.text():
                config['api_key_obfuscated'] = base64.b64encode(
                    self.api_key_edit.text().encode('utf-8')
                ).decode('utf-8')

            # Salvar workers e timeout
            if hasattr(self, 'workers_spin'):
                config['workers'] = self.workers_spin.value()
            if hasattr(self, 'timeout_spin'):
                config['timeout'] = self.timeout_spin.value()

            config_file = ProjectConfig.CONFIG_FILE if hasattr(ProjectConfig, 'CONFIG_FILE') else Path("translator_config.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Erro ao salvar config: {e}")

    def log(self, message: str):
        """Adiciona mensagem ao log com timestamp"""
        if hasattr(self, 'log_text'):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.append(f"[{timestamp}] {message}")

    def restart_application(self):
        """Reinicia a aplicação"""
        QMessageBox.information(self, "Reiniciar", "A aplicação será reiniciada.")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def closeEvent(self, event):
        """Evento de fechamento - salva config antes de sair"""
        self.save_config()
        event.accept()


# ================== MAIN ==================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Configurar fonte padrão
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    # Aplicar tema padrão (será sobrescrito pela configuração salva)
    ThemeManager.apply(app, "Preto (Black)")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
