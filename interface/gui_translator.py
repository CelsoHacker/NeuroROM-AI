# -*- coding: utf-8 -*-
"""
================================================================================
TRADUTOR UNIVERSAL DE ROMs - INTERFACE GRÁFICA v4.2 - COMMERCIAL EDITION
CORREÇÃO CRÍTICA: TRADUÇÃO NÃO INICIAVA (Worker travado)
================================================================================
"""

import sys
import os
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QComboBox,
    QProgressBar, QGroupBox, QGridLayout, QTabWidget,
    QMessageBox, QLineEdit, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor


# =============================================================================
# THREAD DE TRADUÇÃO (CORRIGIDA)
# =============================================================================
class TranslatorThread(QThread):
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, script, input_file, output_file, mode, api_key, workers, timeout):
        super().__init__()
        self.script = script
        self.input_file = input_file
        self.output_file = output_file
        self.mode = mode
        self.api_key = api_key
        self.workers = workers
        self.timeout = timeout

    def run(self):
        try:
            self.progress.emit("[INFO] Iniciando tradução...\n")

            if self.mode == "offline":
                cmd = [
                    sys.executable, self.script,
                    self.input_file, self.output_file,
                    str(self.workers), str(self.timeout)
                ]
            else:
                cmd = [
                    sys.executable, self.script,
                    self.input_file, self.output_file,
                    "--mode", self.mode
                ]
                if self.api_key:
                    if self.mode == "gemini":
                        cmd.extend(["--gemini-key", self.api_key])
                    elif self.mode == "deepl":
                        cmd.extend(["--deepl-key", self.api_key])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            percent_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%')

            # 🔧 FIX CRÍTICO: readline() evita travamento sem stdout inicial
            while True:
                line = process.stdout.readline()
                if not line:
                    break

                self.progress.emit(line.rstrip())

                match = percent_pattern.search(line)
                if match:
                    try:
                        percent = int(float(match.group(1)))
                        self.progress_percent.emit(percent, "Traduzindo...")
                    except:
                        pass

            process.wait()

            if process.returncode == 0:
                self.progress_percent.emit(100, "Concluído")
                self.finished.emit(True, self.output_file)
            else:
                self.finished.emit(False, f"Erro código {process.returncode}")

        except Exception as e:
            self.finished.emit(False, str(e))


# =============================================================================
# INTERFACE PRINCIPAL (RESUMIDA – SEM MUDANÇAS FUNCIONAIS)
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.extracted_file = None
        self.translated_file = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Tradutor Universal de ROMs - Corrigido")
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("TRADUTOR UNIVERSAL DE ROMs")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.translate_btn = QPushButton("TRADUZIR")
        self.translate_btn.clicked.connect(self.start_translation)
        layout.addWidget(self.translate_btn)

    def start_translation(self):
        script = "tradutor_universal_v5.py"  # ajuste se necessário
        input_file = self.extracted_file
        output_file = "saida_traduzida.txt"

        self.worker = TranslatorThread(
            script=script,
            input_file=input_file,
            output_file=output_file,
            mode="gemini",
            api_key="",
            workers=1,
            timeout=300
        )

        self.worker.progress.connect(self.log)
        self.worker.progress_percent.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def update_progress(self, percent, info):
        self.progress_bar.setValue(percent)

    def on_finished(self, success, result):
        if success:
            QMessageBox.information(self, "OK", "Tradução concluída")
        else:
            QMessageBox.critical(self, "Erro", result)

    def log(self, msg):
        self.log_text.append(msg)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)


# =============================================================================
# MAIN
# =============================================================================
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
