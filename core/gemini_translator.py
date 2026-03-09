#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Online Translator - Mixin Module
========================================
Translation methods using Google Gemini API for ROM Translation Framework.
These methods are designed to be mixed into a GUI class.

Author: ROM Translation Framework Team
License: MIT
"""

import os
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _sanitize_error(msg) -> str:
    """Remove possíveis API keys / tokens de mensagens de erro."""
    s = str(msg)
    s = re.sub(r'AIza[0-9A-Za-z\-_]{10,}', '[REDACTED]', s)
    s = re.sub(r'([?&]key=)[^&\s]+', r'\1[REDACTED]', s)
    s = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{10,}', r'\1[REDACTED]', s)
    s = re.sub(r'sk-[A-Za-z0-9]{10,}', 'sk-[REDACTED]', s)
    return s

# Third-party imports - Qt6
try:
    from PyQt6.QtWidgets import QMessageBox, QApplication
    from PyQt6.QtCore import Qt
except ImportError:
    pass

# Third-party imports - Gemini
try:
    from google import genai
except ImportError:
    pass

# Local imports
try:
    from interface.gui_translator import check_ollama_health_detailed, ProjectConfig, ThemeManager
except ImportError:
    try:
        from gui_translator import check_ollama_health_detailed, ProjectConfig, ThemeManager
    except ImportError:
        # Fallback: define placeholder functions
        def check_ollama_health_detailed():
            return False, "Module not available", ""

        class ProjectConfig:
            BASE_DIR = Path('.')
            FRAMEWORK_DIR = BASE_DIR
            CORE_DIR = FRAMEWORK_DIR / 'core'
            EXTRACTION_DIR = CORE_DIR

        class ThemeManager:
            pass


# =============================================================
# GEMINI ONLINE TRANSLATOR
# =============================================================
def translate_with_gemini(self):
    """
    Online translation using Google Gemini API.
    
    This method should be mixed into a GUI class that has:
    - self.extracted_file: Path to input text file
    - self.translated_file: Path to output file (will be set)
    - self.log(): Logging method
    - self.statusBar(): Qt status bar
    """
    try:
        from google import genai
    except Exception:
        QMessageBox.critical(
            self,
            "Gemini não encontrado",
            "A biblioteca oficial do Gemini não está instalada.\n\n"
            "Instale com:\n"
            "pip install google-genai"
        )
        return

    if not self.extracted_file:
        QMessageBox.warning(self, "Aviso", "Selecione um arquivo extraído primeiro!")
        return

    # Load texts from file
    try:
        with open(self.extracted_file, "r", encoding="utf-8", errors="ignore") as f:
            original_text = f.read()
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao ler arquivo:\n{_sanitize_error(e)}")
        return

    # Get source and target languages from UI (if available)
    source_lang_code = getattr(self, 'source_language_code', 'auto')
    target_lang_code = getattr(self, 'target_language_code', 'pt')

    # Language names for prompts (full names for Gemini)
    LANG_NAMES = {
        'pt': 'Portuguese (Brazil)', 'en': 'English (US)', 'es': 'Spanish (Spain)',
        'fr': 'French (France)', 'de': 'German (Germany)', 'it': 'Italian (Italy)',
        'ja': 'Japanese (日本語)', 'ko': 'Korean (한국어)', 'zh': 'Chinese (中文)',
        'ru': 'Russian (Русский)', 'ar': 'Arabic (العربية)', 'hi': 'Hindi (हिन्दी)',
        'tr': 'Turkish (Türkçe)', 'pl': 'Polish (Polski)', 'nl': 'Dutch (Nederlands)',
        'auto': 'AUTO-DETECT'
    }

    source_lang_full = LANG_NAMES.get(source_lang_code, source_lang_code)
    target_lang_full = LANG_NAMES.get(target_lang_code, target_lang_code)

    # Prepare universal translation prompt (works for ANY language pair)
    prompt = f"""
    Translate the text below COMPLETELY into {target_lang_full}.
    Preserve proper names, formatting, line breaks, and style.
    Be accurate, natural, and consistent with retro games terminology.

    TEXT:
    {original_text}
    """

    # Initialize Gemini client
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao inicializar Gemini:\n{_sanitize_error(e)}")
        return

    self.log("[GEMINI] Iniciando tradução online...")
    self.statusBar().showMessage("Traduzindo com Gemini...")

    # Execute translation
    try:
        response = client.models.generate(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        translated_text = response.text
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao traduzir com Gemini:\n{_sanitize_error(e)}")
        return

    # Save translated text
    output_path = ProjectConfig.BASE_DIR / "gemini_translation.txt"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao salvar arquivo:\n{_sanitize_error(e)}")
        return

    # Update GUI state
    self.translated_file = str(output_path)
    self.translated_file_label.setText(output_path.name)
    self.translated_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    self.log("[GEMINI] Tradução concluída!")
    QMessageBox.information(self, "Gemini", "Tradução concluída com sucesso!")


def translate_texts(self):
    """
    Execute translation, choosing between Gemini Online or Ollama Offline.
    
    Detects selected mode from GUI and routes to appropriate backend.
    """
    # Detect selected translation mode
    mode = self.translation_mode_combo.currentText()

    # Route to Gemini for online mode
    if "Online" in mode:
        return self.translate_with_gemini()

    # ------------------------------------------------------------
    # FULL TRANSLATION (Offline mode with Ollama)
    # ------------------------------------------------------------

    # Validate Ollama availability
    health_ok, health_msg, icon = check_ollama_health_detailed()

    if not health_ok:
        QMessageBox.critical(
            self,
            "Ollama Offline",
            f"O Ollama não está disponível.\n\n{health_msg}\n\n"
            "Certifique-se de que:\n"
            "1. Ollama está instalado\n"
            "2. O serviço está rodando\n"
            "3. O modelo 'gemma:2b' está baixado"
        )
        return

    # Continue with Ollama offline translation
    if not self.extracted_file:
        QMessageBox.warning(self, "Aviso", "Selecione um arquivo extraído primeiro!")
        return

    # Read extracted text
    try:
        with open(self.extracted_file, "r", encoding="utf-8", errors="ignore") as f:
            extracted_text = f.read()
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao ler arquivo extraído:\n{_sanitize_error(e)}")
        return

    # Split into individual texts for translation
    text_lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
    
    if not text_lines:
        QMessageBox.warning(self, "Aviso", "Nenhum texto encontrado no arquivo extraído!")
        return

    self.log(f"[OFFLINE] Iniciando tradução de {len(text_lines)} textos...")
    self.statusBar().showMessage(f"Traduzindo {len(text_lines)} textos com Ollama...")

    # Get translation parameters from GUI
    workers = self.workers_spin.value()
    timeout = self.timeout_spin.value()

    # Import parallel translator
    try:
        from parallel_translator import ParallelTranslator
    except ImportError:
        QMessageBox.critical(
            self,
            "Erro",
            "Módulo 'parallel_translator' não encontrado.\n\n"
            "Verifique a estrutura do projeto."
        )
        return

    # Initialize translator
    translator = ParallelTranslator(
        model_name="gemma:2b",
        num_workers=workers,
        timeout_seconds=timeout
    )

    # Start translation
    self.log(f"[CONFIG] Workers: {workers} | Timeout: {timeout}s")
    
    try:
        translated_lines = translator.translate_batch(text_lines)
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha na tradução:\n{_sanitize_error(e)}")
        return

    # Save results
    output_path = ProjectConfig.BASE_DIR / "ollama_translation.txt"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(translated_lines))
    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Falha ao salvar tradução:\n{_sanitize_error(e)}")
        return

    # Update GUI
    self.translated_file = str(output_path)
    self.translated_file_label.setText(output_path.name)
    self.translated_file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    self.log("[OFFLINE] Tradução concluída!")
    QMessageBox.information(
        self,
        "Sucesso",
        f"Tradução concluída!\n\n"
        f"Textos processados: {len(translated_lines)}\n"
        f"Arquivo salvo: {output_path.name}"
    )


def strip_accents_for_rom(text: str) -> str:
    """Remove acentos quando a fonte da ROM não suporta PT-BR."""
    if not isinstance(text, str) or not text:
        return ""
    replacements = {
        "ã": "a",
        "ê": "e",
        "ç": "c",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "â": "a",
        "õ": "o",
        "à": "a",
        "Ã": "A",
        "Ê": "E",
        "Ç": "C",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Â": "A",
        "Õ": "O",
        "À": "A",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _safe_json_load(path: str) -> dict:
    try:
        if not path or not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _extract_font_has_pt_br(payload: dict) -> bool | None:
    if not isinstance(payload, dict):
        return None
    candidates = [
        payload.get("font_has_pt_br"),
        (payload.get("font_profile") or {}).get("font_has_pt_br") if isinstance(payload.get("font_profile"), dict) else None,
        (payload.get("font_profile") or {}).get("has_pt_br") if isinstance(payload.get("font_profile"), dict) else None,
        (payload.get("profile") or {}).get("font_has_pt_br") if isinstance(payload.get("profile"), dict) else None,
        (payload.get("profile") or {}).get("has_pt_br") if isinstance(payload.get("profile"), dict) else None,
    ]
    for val in candidates:
        if isinstance(val, bool):
            return bool(val)
    return None


def _should_strip_accents_for_context(input_path: str | None = None) -> bool:
    env_flag = str(os.environ.get("NEUROROM_FONT_HAS_PT_BR", "") or "").strip().lower()
    if env_flag in {"1", "true", "yes", "on"}:
        return False
    if env_flag in {"0", "false", "no", "off"}:
        return True

    profile_env = str(os.environ.get("NEUROROM_PROFILE_JSON", "") or "").strip()
    if profile_env:
        flag = _extract_font_has_pt_br(_safe_json_load(profile_env))
        if isinstance(flag, bool):
            return not flag

    candidates = []
    if isinstance(input_path, str) and input_path.strip():
        p = os.path.abspath(input_path)
        root, _ = os.path.splitext(p)
        candidates.extend(
            [
                f"{root}.profile.json",
                f"{root}_profile.json",
                f"{root}.meta.json",
                f"{root}_meta.json",
            ]
        )
    for c in candidates:
        flag = _extract_font_has_pt_br(_safe_json_load(c))
        if isinstance(flag, bool):
            return not flag

    # Sem declaração explícita, considera sem suporte PT-BR.
    return True


def _apply_strip_accents_to_file_if_needed(
    output_path: str | None,
    context_path: str | None = None,
) -> bool:
    if not isinstance(output_path, str) or not output_path.strip():
        return False
    if not os.path.isfile(output_path):
        return False
    if not _should_strip_accents_for_context(context_path):
        return False
    try:
        with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()
        stripped = strip_accents_for_rom(original)
        if stripped == original:
            return False
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(stripped)
        return True
    except Exception:
        return False


_ORIGINAL_TRANSLATE_WITH_GEMINI = translate_with_gemini
_ORIGINAL_TRANSLATE_TEXTS = translate_texts


def translate_with_gemini(self):
    """
    Wrapper runtime: mantém comportamento original e aplica política de acentos
    conforme suporte de fonte da ROM.
    """
    result = _ORIGINAL_TRANSLATE_WITH_GEMINI(self)
    out_file = getattr(self, "translated_file", None)
    ctx_file = getattr(self, "extracted_file", None)
    changed = _apply_strip_accents_to_file_if_needed(out_file, ctx_file)
    if changed and hasattr(self, "log"):
        try:
            self.log("[GEMINI] Pós-processamento: strip_accents_for_rom aplicado.")
        except Exception:
            pass
    return result


def translate_texts(self):
    """
    Wrapper runtime: mantém comportamento original e aplica política de acentos
    após tradução online/offline.
    """
    result = _ORIGINAL_TRANSLATE_TEXTS(self)
    out_file = getattr(self, "translated_file", None)
    ctx_file = getattr(self, "extracted_file", None)
    changed = _apply_strip_accents_to_file_if_needed(out_file, ctx_file)
    if changed and hasattr(self, "log"):
        try:
            self.log("[TRADUÇÃO] Pós-processamento: strip_accents_for_rom aplicado.")
        except Exception:
            pass
    return result


# =============================================================
# MAIN WINDOW CLASS (Example usage)
# =============================================================
# The methods above should be mixed into your MainWindow class:
#
# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         # ... GUI setup ...
#     
#     # Mix in translation methods
#     translate_with_gemini = translate_with_gemini
#     translate_texts = translate_texts
#     
#     # ... rest of your implementation ...
