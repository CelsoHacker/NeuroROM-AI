"""Aba de extração e utilidades de análise para o módulo GUI."""
# -*- coding: utf-8 -*-
# pylint: disable=C0301,C0302,C0304,C0103,C0114,C0115,C0116,C0411,C0415,R0902,R0903,R0911,R0912,R0913,R0914,R0915,R0917,R1705,W0130,W0201,W0718,W1309
# Motivo: arquivo legado e extenso; ajustes estruturais serão feitos em refatorações futuras.
import os
import json
import struct
import math
import re
import numpy as np
from collections import Counter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog,
    QMessageBox, QProgressBar, QSpinBox, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal

# ================================================================
# CRIPTOANÁLISE DE DESLOCAMENTO - Dicionário de palavras SNES
# ================================================================
SNES_VOCABULARY = {
    # Core UI & Menu
    'START', 'SELECT', 'OPTION', 'CONFIG', 'CONTINUE', 'SAVE', 'LOAD',
    'YES', 'NO', 'OK', 'CANCEL', 'BACK', 'EXIT', 'RETURN', 'RESTART',

    # Game States
    'GAME', 'OVER', 'PAUSE', 'TIME', 'SCORE', 'HIGH', 'LOW', 'WIN', 'LOSE',
    'VICTORY', 'DEFEAT', 'CLEAR', 'COMPLETE', 'FINISH', 'MISSION',

    # Character & Entities
    'MARIO', 'YOSHI', 'PRINCESS', 'PEACH', 'BOWSER', 'KOOPA', 'GOOMBA',
    'TOAD', 'LUIGI', 'DONKEY', 'KONG', 'LINK', 'ZELDA', 'SAMUS', 'KIRBY',

    # Game Elements
    'COIN', 'LIFE', 'LIVES', 'HEART', 'HEALTH', 'HP', 'MP', 'EXP', 'LEVEL',
    'STAGE', 'WORLD', 'AREA', 'MAP', 'ROOM', 'BOSS', 'ENEMY', 'PLAYER',
    'ITEM', 'WEAPON', 'ARMOR', 'POTION', 'KEY', 'DOOR', 'CHEST', 'TREASURE',

    # Controls & Actions
    'UP', 'DOWN', 'LEFT', 'RIGHT', 'JUMP', 'RUN', 'ATTACK', 'DEFEND',
    'THROW', 'CATCH', 'SHOOT', 'HIT', 'MOVE', 'PRESS', 'BUTTON',

    # Story & Dialogue
    'WELCOME', 'HELLO', 'HEY', 'THANK', 'SORRY', 'PLEASE', 'HELP', 'LOOK',
    'LISTEN', 'WAIT', 'STOP', 'GO', 'FIND', 'TAKE', 'USE', 'TALK',

    # Stats & Attributes
    'STRENGTH', 'DEFENSE', 'SPEED', 'AGILITY', 'INTELLIGENCE', 'MAGIC',
    'POWER', 'ENERGY', 'POINTS', 'RANK', 'CLASS', 'TYPE', 'SKILL',

    # Common Phrases
    'GAME OVER', 'PRESS START', 'INSERT COIN', 'CONTINUE?', 'SAVE GAME',
    'LOAD GAME', 'OPTION MENU', 'SOUND TEST', 'CREDITS', 'THE END'
}

# ================================================================
# BASE DE ASSINATURAS FORENSES (Magic Bytes Database)
# ================================================================
FORENSIC_SIGNATURES = {
    # === CONSOLE ROMS ===
    b'\xAA\xBB\x04': ('SNES Header (LoROM)', 'CONSOLE'),
    b'\xAA\xBB\x05': ('SNES Header (HiROM)', 'CONSOLE'),
    b'NES\x1A': ('NES ROM', 'CONSOLE'),

    # === GAME ENGINES ===
    b'UnityFS': ('Unity Engine', 'PC_GAME'),
    b'Unity': ('Unity Engine (Legacy)', 'PC_GAME'),
    b'UE4': ('Unreal Engine 4', 'PC_GAME'),
    b'UE3': ('Unreal Engine 3', 'PC_GAME'),
    b'Source Engine': ('Source Engine (Valve)', 'PC_GAME'),

    # === ARCHIVES & COMPRESSION ===
    b'PK\x03\x04': ('ZIP Archive', 'ARCHIVE'),
    b'Rar!\x1a\x07\x00': ('RAR Archive', 'ARCHIVE'),
    b'\x1F\x8B': ('GZIP Compressed', 'ARCHIVE'),
    b'BZh': ('BZIP2 Compressed', 'ARCHIVE'),
}

# ============================================================================
# LINGUISTIC VALIDATION ENGINE (Coração do Sistema)
# ============================================================================
class LinguisticValidator:
    """
    Motor de Validação Heurística baseado em Estrutura Linguística.

    Regras implementadas:
    1. Criptoanálise de Deslocamento (Shift -20 a +20)
    2. Validação de Razão Letra/Símbolo (>80% letras ou espaços)
    3. Filtro de Densidade de Vogais (25%-60% para textos >5 chars)
    4. Blacklist de Entropia (Shannon)
    5. Detecção de Bigramas Linguísticos Inválidos
    """

    # Consoantes raras em inglês (padrões inválidos)
    RARE_CONSONANTS = {'q', 'x', 'z', 'j', 'v', 'w', 'k', 'y'}

    # Bigramas impossíveis em linguagem natural
    IMPOSSIBLE_BIGRAMS = {
        'vq', 'qw', 'qj', 'jx', 'xz', 'zq', 'qk', 'kq',
        'wv', 'vw', 'wx', 'xw', 'zj', 'jz', 'qy', 'yq'
    }

    # Trigramas inválidos
    IMPOSSIBLE_TRIGRAMS = {
        'vqw', 'jxz', 'tkp', 'ghq', 'wvq', 'xjk', 'qgh', 'zxj',
        'vvv', 'jjj', 'qqq', 'xxx', 'zzz', 'kkk', 'www', 'vvv'
    }

    @staticmethod
    def detect_best_shift(data_sample):
        """
        Criptoanálise de Deslocamento: Testa shifts de -20 a +20.
        Retorna o shift que produz a maior densidade de palavras reconhecíveis.
        """
        best_shift = 0
        best_score = -1

        for shift in range(-20, 21):
            if shift == 0:
                continue

            # Aplica shift inverso para testar
            test_strings = []
            for i in range(0, len(data_sample) - 10, 10):
                chunk = data_sample[i:i+20]
                test_str = ''.join(chr((b + shift) & 0xFF) if 32 <= (b + shift) <= 126 else ' '
                                 for b in chunk)
                test_strings.append(test_str)

            # Conta palavras reconhecíveis
            score = 0
            all_test_text = ' '.join(test_strings).upper()

            for word in SNES_VOCABULARY:
                if len(word) >= 4:  # Só palavras significativas
                    if word in all_test_text:
                        score += len(word) * 2  # Peso por comprimento

            if score > best_score:
                best_score = score
                best_shift = shift

        return best_shift if best_score > 10 else 0  # Threshold mínimo

    @staticmethod
    def calculate_letter_ratio(text):
        """Calcula a razão letra/símbolo (>80% ideal)."""
        if not text:
            return 0.0

        letter_count = sum(1 for c in text if c.isalpha() or c.isspace())
        return letter_count / len(text)

    @staticmethod
    def calculate_vowel_density(text):
        """Calcula densidade de vogais (25%-60% ideal para inglês)."""
        vowels = set('aeiouAEIOU')
        letters = [c for c in text if c.isalpha()]

        if not letters:
            return 0.0

        vowel_count = sum(1 for c in letters if c in vowels)
        return vowel_count / len(letters)

    @staticmethod
    def has_valid_vowel_ratio(text):
        """
        Filtro de Densidade de Vogais.
        Strings >5 caracteres DEVEM ter 25%-60% de vogais.
        """
        if len(text) <= 5:
            return True  # Curto demais para julgar

        ratio = LinguisticValidator.calculate_vowel_density(text)
        return 0.20 <= ratio <= 0.65  # Margem ligeiramente mais ampla

    @staticmethod
    def has_invalid_consonant_clusters(text):
        """Detecta clusters de consoantes raras/impossíveis."""
        text_lower = text.lower()

        # Verifica bigramas impossíveis
        for i in range(len(text_lower) - 1):
            bigram = text_lower[i:i+2]
            if bigram in LinguisticValidator.IMPOSSIBLE_BIGRAMS:
                return True

        # Verifica trigramas impossíveis
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i:i+3]
            if trigram in LinguisticValidator.IMPOSSIBLE_TRIGRAMS:
                return True

        # Verifica 4+ consoantes seguidas (muito raro em inglês)
        consonants = 0
        for char in text_lower:
            if char in 'bcdfghjklmnpqrstvwxyz':
                consonants += 1
                if consonants >= 4:
                    return True
            else:
                consonants = 0

        return False

    @staticmethod
    def calculate_shannon_entropy(text):
        """Calcula Entropia de Shannon para detectar repetição/caos."""
        if not text:
            return 0.0

        # Normaliza para minúsculas para análise de repetição
        text = text.lower()

        # Calcula frequência
        freq = Counter(text)
        entropy = 0.0
        length = len(text)

        for count in freq.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy

    @staticmethod
    def has_valid_entropy(text):
        """
        Filtro de Entropia:
        - Baixa entropia: repetição (ex: "AAAAA")
        - Alta entropia: caos binário (ex: "x7f\u0012")
        """
        if len(text) < 4:
            return True  # Muito curto para análise

        entropy = LinguisticValidator.calculate_shannon_entropy(text)

        # Textos curtos (2-10 chars)
        if len(text) <= 10:
            return 1.5 <= entropy <= 4.5

        # Textos médios (11-30 chars)
        elif len(text) <= 30:
            return 2.5 <= entropy <= 5.0

        # Textos longos (>30 chars)
        else:
            return 3.0 <= entropy <= 5.5

    @staticmethod
    def is_linguistic(text, min_length=3):
        """
        VALIDAÇÃO PRINCIPAL: Verifica se o texto é linguagem humana.

        Retorna (is_valid, category, score)
        Category: 'word', 'phrase', 'garbage'
        """
        # 0. Comprimento mínimo
        if len(text) < min_length:
            return False, 'garbage', 0.0

        score = 0.0

        # 1. Whitelist de palavras curtas de jogos
        SHORT_GAME_WORDS = {'UP', 'ON', 'OFF', 'YES', 'NO', 'OK', 'HP', 'MP',
                          'LV', 'XP', 'STR', 'DEX', 'AGI', 'INT', 'P1', 'P2'}

        if text.upper() in SHORT_GAME_WORDS:
            return True, 'word', 1.0

        # 2. Razão Letra/Símbolo (>80% ideal)
        letter_ratio = LinguisticValidator.calculate_letter_ratio(text)
        if letter_ratio > 0.8:
            score += 0.30
        elif letter_ratio > 0.6:
            score += 0.15
        else:
            return False, 'garbage', score

        # 3. Densidade de Vogais (25%-60% ideal)
        if LinguisticValidator.has_valid_vowel_ratio(text):
            score += 0.25
        else:
            score -= 0.15

        # 4. Sem clusters inválidos de consoantes
        if not LinguisticValidator.has_invalid_consonant_clusters(text):
            score += 0.20

        # 5. Entropia válida (nem repetitiva nem caótica)
        if LinguisticValidator.has_valid_entropy(text):
            score += 0.25
        else:
            score -= 0.20

        # 6. Caracteres imprimíveis
        printable_ratio = sum(1 for c in text if c.isprintable()) / len(text)
        if printable_ratio > 0.9:
            score += 0.10

        # 7. Categorização
        has_spaces = ' ' in text
        word_count = len(text.split())

        if has_spaces and word_count >= 2:
            category = 'phrase'
            # Frases completas ganham bônus
            if len(text) > 10:
                score += 0.10
        else:
            category = 'word'

        # 8. Filtros finais
        # Rejeita códigos/endereços
        if text.startswith(('0x', '$', '&H', '\\x')):
            return False, 'garbage', score

        # Rejeita URLs/paths
        if any(x in text.lower() for x in ['http://', 'https://', 'c:\\', 'www.', '.exe', '.dll']):
            return False, 'garbage', score

        # Threshold final
        if score >= 0.6:
            return True, category, score
        else:
            return False, 'garbage', score

# ============================================================================
# UNIVERSAL STRING SCANNER (Com Heurística Linguística)
# ============================================================================
class UniversalStringScanner:
    """
    Scanner Heurístico Dual-Core com Validação Linguística.
    """

    CHUNK_SIZE = 2 * 1024 * 1024  # 2MB por chunk
    OVERLAP_SIZE = 512  # 512 bytes de overlap

    def __init__(self, file_path, min_length=3, sampling_mode=False, cancel_flag=None):
        self.file_path = file_path
        self.min_length = min_length
        self.sampling_mode = sampling_mode
        self.cancel_flag = cancel_flag

        # Detecção de encoding
        self.detected_shift = 0
        self.is_snes = file_path.lower().endswith(('.smc', '.sfc'))

        # Estatísticas
        self.linguistic_strings = 0
        self.garbage_strings = 0

    def extract(self, progress_callback=None):
        """Extrai strings com validação linguística em tempo real."""
        import time

        try:
            file_size = os.path.getsize(self.file_path)
            start_time = time.time()

            if progress_callback:
                progress_callback(5, "[LINGUÍSTICA] Inicializando motor de validação...")
                progress_callback(10, f"[SISTEMA] Tamanho do arquivo: {file_size:,} bytes")

            # FASE 1: Análise criptográfica para SNES
            if self.is_snes:
                if progress_callback:
                    progress_callback(15, "[CRIPTOANÁLISE] Testando deslocamentos ASCII (-20...+20)...")

                with open(self.file_path, 'rb') as f:
                    sample_data = f.read(65536)  # 64KB para análise

                self.detected_shift = LinguisticValidator.detect_best_shift(sample_data)

                if self.detected_shift != 0:
                    if progress_callback:
                        progress_callback(18, f"[CRIPTOANÁLISE] Melhor shift encontrado: {self.detected_shift:+d}")
                else:
                    if progress_callback:
                        progress_callback(18, "[CRIPTOANÁLISE] Nenhum shift significativo detectado (ASCII puro?)")

            # FASE 2: Escaneamento com chunks
            all_strings = []
            chunk_stats = {'words': 0, 'phrases': 0, 'garbage': 0}

            total_chunks = (file_size // self.CHUNK_SIZE) + 1

            with open(self.file_path, 'rb') as f:
                position = 0
                chunk_index = 0

                while position < file_size:
                    # Verificação de cancelamento
                    if self.cancel_flag and self.cancel_flag.is_set():
                        return {'strings': [], 'total': 0, 'cancelled': True}

                    # Lê chunk
                    f.seek(position)
                    chunk_data = f.read(self.CHUNK_SIZE + self.OVERLAP_SIZE)

                    if not chunk_data:
                        break

                    chunk_index += 1

                    # Atualiza progresso
                    if progress_callback and chunk_index % 5 == 0:
                        progress = 20 + int((position / file_size) * 60)
                        progress_callback(progress,
                            f"[SCAN] Chunk {chunk_index}/{total_chunks} | "
                            f"Pos: {position:,} bytes | "
                            f"Strings válidas: {self.linguistic_strings}")

                    # Extrai strings brutas (ASCII)
                    raw_strings = self._extract_raw_strings(chunk_data)

                    # Processa cada string com validação linguística
                    for text in raw_strings:
                        # Aplica shift se necessário
                        if self.detected_shift != 0:
                            text = self._apply_shift(text)

                        # Validação linguística
                        is_valid, category, score = LinguisticValidator.is_linguistic(text, self.min_length)

                        if is_valid:
                            self.linguistic_strings += 1
                            chunk_stats['words' if category == 'word' else 'phrases'] += 1

                            all_strings.append({
                                'text': text,
                                'category': category,
                                'score': round(score, 3),
                                'shift': self.detected_shift
                            })
                        else:
                            self.garbage_strings += 1
                            chunk_stats['garbage'] += 1

                    position += self.CHUNK_SIZE

            # Remove duplicatas mantendo a de maior score
            unique_strings = []
            seen_texts = set()

            for s in sorted(all_strings, key=lambda x: x['score'], reverse=True):
                text = s['text']
                if text not in seen_texts and len(text) >= self.min_length:
                    seen_texts.add(text)
                    unique_strings.append(s)

            # Categoriza para saída final
            result_strings = []
            word_id = 0

            for i, s in enumerate(unique_strings):
                result_strings.append({
                    'id': word_id,
                    'pointer_index': word_id,
                    'table_offset': 0,
                    'rom_offset': 0,
                    'snes_addr': f"LINGUISTIC:{s['category'].upper()}",
                    'original': s['text'],
                    'translated': '',
                    'category': s['category'],
                    'confidence': s['score']
                })
                word_id += 1

            # Estatísticas finais
            elapsed_time = time.time() - start_time

            if progress_callback:
                word_count = sum(1 for s in unique_strings if s['category'] == 'word')
                phrase_count = sum(1 for s in unique_strings if s['category'] == 'phrase')

                progress_callback(100,
                    f"[CONCLUÍDO] Linguística aplicada!\n"
                    f"• Palavras: {word_count} | Frases: {phrase_count}\n"
                    f"• Lixo descartado: {self.garbage_strings:,}\n"
                    f"• Tempo: {elapsed_time:.1f}s | "
                    f"Shift: {self.detected_shift:+d}")

            return {
                'strings': result_strings,
                'total': len(result_strings),
                'stats': {
                    'words': word_count,
                    'phrases': phrase_count,
                    'garbage': self.garbage_strings,
                    'shift': self.detected_shift
                }
            }

        except Exception as e:
            return {'error': f'Erro no scanner linguístico: {str(e)}'}

    def _extract_raw_strings(self, data):
        """Extrai strings brutas do chunk binário."""
        strings = []
        current = []

        for byte in data:
            # ASCII imprimível
            if 32 <= byte <= 126:
                current.append(chr(byte))
            else:
                # Terminador encontrado
                if len(current) >= self.min_length:
                    text = ''.join(current)
                    # Filtro básico de comprimento
                    if len(text.strip()) >= self.min_length:
                        strings.append(text)
                current = []

        # String final no buffer
        if len(current) >= self.min_length:
            text = ''.join(current)
            if len(text.strip()) >= self.min_length:
                strings.append(text)

        return strings

    def _apply_shift(self, text):
        """Aplica o shift de deslocamento detectado."""
        if self.detected_shift == 0:
            return text

        result = []
        for char in text:
            if 'A' <= char <= 'Z':
                # Aplica shift com wrap-around no alfabeto
                shifted = ord(char) + self.detected_shift
                if shifted > ord('Z'):
                    shifted -= 26
                elif shifted < ord('A'):
                    shifted += 26
                result.append(chr(shifted))
            elif 'a' <= char <= 'z':
                shifted = ord(char) + self.detected_shift
                if shifted > ord('z'):
                    shifted -= 26
                elif shifted < ord('a'):
                    shifted += 26
                result.append(chr(shifted))
            else:
                result.append(char)

        return ''.join(result)

# ============================================================================
# EXTRACTION WORKER (Com Motor Linguístico)
# ============================================================================
class ExtractionWorker(QThread):
    """
    Worker com motor de validação linguística.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)

    def __init__(self, rom_path, pointer_offset, num_entries,
                 sampling_mode=False, linguistic_mode=True, parent=None):
        super().__init__(parent)
        self.rom_path = rom_path
        self.pointer_offset = pointer_offset
        self.num_entries = num_entries
        self.sampling_mode = sampling_mode
        self.linguistic_mode = linguistic_mode

        import threading
        self.cancel_flag = threading.Event()

    def cancel(self):
        """Cancela a operação."""
        self.cancel_flag.set()
        self.progress.emit(0, "[CANCELANDO] Finalizando operação...")

    def run(self):
        try:
            self.progress.emit(1, f"[SISTEMA] Arquivo: {os.path.basename(self.rom_path)}")
            self.progress.emit(2, f"[SISTEMA] Modo: {'Linguístico' if self.linguistic_mode else 'Tradicional'}")

            # SMART ROUTER aprimorado
            file_ext = os.path.splitext(self.rom_path)[1].lower()

            # Rota 1: SNES com validação linguística
            if file_ext in ['.smc', '.sfc'] and self.linguistic_mode:
                self.progress.emit(3, "[ROTA] SNES detectado → Ativando motor linguístico")
                result = self._extract_with_linguistic()

            # Rota 2: Scanner universal com heurística
            else:
                self.progress.emit(3, "[ROTA] Usando scanner universal com heurística")
                result = self._extract_universal()

            self.finished.emit(result)

        except Exception as e:
            self.progress.emit(0, f"ERRO: {str(e)}")
            self.finished.emit({'strings': [], 'total': 0, 'error': str(e)})

    def _extract_with_linguistic(self):
        """Extrai usando o motor linguístico."""
        scanner = UniversalStringScanner(
            self.rom_path,
            min_length=2,  # Aceita 'UP', 'ON'
            sampling_mode=self.sampling_mode,
            cancel_flag=self.cancel_flag
        )
        return scanner.extract(progress_callback=self.progress.emit)

    def _extract_universal(self):
        """Fallback para scanner universal."""
        scanner = UniversalStringScanner(
            self.rom_path,
            min_length=3,
            sampling_mode=self.sampling_mode,
            cancel_flag=self.cancel_flag
        )
        return scanner.extract(progress_callback=self.progress.emit)

# ============================================================================
# EXTRACTION TAB (Interface com Análise Linguística)
# ============================================================================
class ExtractionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.rom_path = None
        self.extracted_data = []
        self.optimized_data = []
        self.linguistic_stats = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QSpinBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14a085;
            }
            QPushButton:pressed {
                background-color: #0a5c5f;
            }
            QTextEdit {
                background-color: #252525;
                color: #00ff88;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                font-family: 'Consolas', monospace;
            }
            QProgressBar {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #0d7377;
            }
            QCheckBox {
                color: #e0e0e0;
                padding: 5px;
            }
        """)

        # Título
        title = QLabel("🔬 EXTRAÇÃO LINGUÍSTICA - HEURÍSTICA HUMANA")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #00ff88;")
        layout.addWidget(title)

        # Seleção de arquivo
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Arquivo:"))
        self.rom_input = QLineEdit()
        self.rom_input.setPlaceholderText("Selecione ROM/arquivo...")
        file_layout.addWidget(self.rom_input)

        btn_browse = QPushButton("📂 BROWSE")
        btn_browse.clicked.connect(self.select_rom)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        # Configurações avançadas
        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("Min Length:"))
        self.min_length = QSpinBox()
        self.min_length.setRange(2, 10)
        self.min_length.setValue(3)
        self.min_length.setToolTip("Comprimento mínimo da string (2 para 'UP', 'ON')")
        config_layout.addWidget(self.min_length)

        # Checkbox de modo linguístico
        self.linguistic_checkbox = QCheckBox("🧠 Validação Linguística")
        self.linguistic_checkbox.setChecked(True)
        self.linguistic_checkbox.setToolTip(
            "Ativa heurística baseada em estrutura linguística:\n"
            "• Densidade de vogais (25-60%)\n"
            "• Razão letra/símbolo (>80%)\n"
            "• Filtro de entropia de Shannon\n"
            "• Detecção de clusters inválidos"
        )
        config_layout.addWidget(self.linguistic_checkbox)

        config_layout.addStretch()
        layout.addLayout(config_layout)

        # Botão de extração principal
        btn_extract = QPushButton("🔍 EXTRAIR COM HEURÍSTICA LINGUÍSTICA")
        btn_extract.setStyleSheet("background-color: #00aa55; padding: 10px; font-size: 11pt;")
        btn_extract.clicked.connect(self.start_linguistic_extraction)
        layout.addWidget(btn_extract)

        # Botão de cancelamento
        self.btn_cancel = QPushButton("⏹️ CANCELAR")
        self.btn_cancel.setStyleSheet("background-color: #aa3333; padding: 8px;")
        self.btn_cancel.clicked.connect(self.cancel_extraction)
        self.btn_cancel.setEnabled(False)
        layout.addWidget(self.btn_cancel)

        # Barra de progresso
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Painel de estatísticas linguísticas
        stats_label = QLabel("📊 ESTATÍSTICAS LINGUÍSTICAS")
        stats_label.setStyleSheet("font-weight: bold; color: #00aaff; margin-top: 10px;")
        layout.addWidget(stats_label)

        self.stats_display = QTextEdit()
        self.stats_display.setMaximumHeight(100)
        self.stats_display.setReadOnly(True)
        layout.addWidget(self.stats_display)

        # Log de processo
        log_label = QLabel("📝 LOG DE PROCESSAMENTO")
        log_label.setStyleSheet("font-weight: bold; color: #00aaff; margin-top: 5px;")
        layout.addWidget(log_label)

        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(120)
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        # Preview categorizado
        preview_label = QLabel("👁️ PREVIEW (Categorizado)")
        preview_label.setStyleSheet("font-weight: bold; color: #00aaff; margin-top: 5px;")
        layout.addWidget(preview_label)

        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        layout.addWidget(self.preview_output)

        # Botões de exportação
        export_layout = QHBoxLayout()

        btn_export_json = QPushButton("💾 JSON (Completo)")
        btn_export_json.clicked.connect(self.export_json)
        export_layout.addWidget(btn_export_json)

        btn_export_txt = QPushButton("📄 TXT (Apenas Texto)")
        btn_export_txt.clicked.connect(self.export_txt)
        export_layout.addWidget(btn_export_txt)

        btn_export_clean = QPushButton("🤖 TXT para IA (Limpo)")
        btn_export_clean.setStyleSheet("background-color: #ff9900;")
        btn_export_clean.clicked.connect(self.export_for_ai)
        btn_export_clean.setToolTip("Exporta apenas texto validado para tradução por IA")
        export_layout.addWidget(btn_export_clean)

        export_layout.addStretch()
        layout.addLayout(export_layout)

    def select_rom(self):
        """Seleciona arquivo ROM."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo", "",
            "Sega Master System (*.sms *.gg *.sg);;"
            "ROMs de Console (*.smc *.sfc *.nes *.gba *.gb *.md *.gen *.bin);;"
            "PC Games (*.exe *.wad *.dat);;"
            "Todos os Arquivos (*.*)"
        )
        if file_path:
            self.rom_path = file_path
            self.rom_input.setText(file_path)
            self.log(f"📁 Arquivo selecionado: {os.path.basename(file_path)}")

    def start_linguistic_extraction(self):
        """Inicia extração com heurística linguística."""
        if not self.rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro!")
            return

        self.log("🚀 INICIANDO EXTRAÇÃO LINGUÍSTICA...")
        self.log("=" * 60)
        self.log("FASE 1: Criptoanálise de Deslocamento (-20...+20)")
        self.log("FASE 2: Validação de Razão Letra/Símbolo (>80%)")
        self.log("FASE 3: Filtro de Densidade de Vogais (25-60%)")
        self.log("FASE 4: Blacklist de Entropia de Shannon")
        self.log("=" * 60)

        self.progress_bar.setValue(0)

        # Cria worker com modo linguístico
        self.worker = ExtractionWorker(
            self.rom_path,
            pointer_offset=0,
            num_entries=0,
            sampling_mode=False,
            linguistic_mode=self.linguistic_checkbox.isChecked()
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)

        self.btn_cancel.setEnabled(True)
        self.worker.start()

    def on_progress(self, value, message):
        """Atualiza progresso."""
        self.progress_bar.setValue(value)
        self.log(message)

    def on_finished(self, result):
        """Processa resultado da extração."""
        self.btn_cancel.setEnabled(False)

        if result.get('cancelled', False):
            self.log("⚠️ EXTRAÇÃO CANCELADA PELO USUÁRIO")
            return

        if 'error' in result:
            QMessageBox.critical(self, "Erro", result['error'])
            return

        self.extracted_data = result['strings']
        self.linguistic_stats = result.get('stats', {})

        total = result['total']
        shift = self.linguistic_stats.get('shift', 0)

        # Atualiza estatísticas
        self.update_stats_display()

        # Log de sucesso
        self.log("✅ EXTRAÇÃO LINGUÍSTICA CONCLUÍDA!")
        self.log(f"• Strings validadas: {total}")
        self.log(f"• Deslocamento detectado: {shift:+d}")

        # Exibe preview categorizado
        self.show_categorized_preview()

        QMessageBox.information(self, "Sucesso",
            f"✅ Heurística Linguística aplicada!\n\n"
            f"Textos válidos: {total}\n"
            f"Deslocamento ASCII: {shift:+d}\n"
            f"Palavras: {self.linguistic_stats.get('words', 0)}\n"
            f"Frases: {self.linguistic_stats.get('phrases', 0)}\n"
            f"Lixo descartado: {self.linguistic_stats.get('garbage', 0):,}")

    def update_stats_display(self):
        """Atualiza display de estatísticas linguísticas."""
        stats = self.linguistic_stats

        text = f"""
╔════════════════════════════════════════╗
║         ANÁLISE LINGUÍSTICA           ║
╠════════════════════════════════════════╣
║ • Palavras isoladas:   {stats.get('words', 0):>6} ║
║ • Frases completas:    {stats.get('phrases', 0):>6} ║
║ • Lixo descartado:     {stats.get('garbage', 0):>6,} ║
║ • Deslocamento ASCII:  {stats.get('shift', 0):>+6d} ║
╚════════════════════════════════════════╝

📊 VALIDAÇÕES APLICADAS:
• Densidade de vogais (25-60%): ✅
• Razão letra/símbolo (>80%): ✅
• Entropia de Shannon: ✅
• Clusters consonantais: ✅
• Bigramas inválidos: ✅
"""
        self.stats_display.setPlainText(text)

    def show_categorized_preview(self):
        """Exibe preview com categorização."""
        if not self.extracted_data:
            return

        preview_lines = []

        # Agrupa por categoria
        words = [s for s in self.extracted_data if s.get('category') == 'word']
        phrases = [s for s in self.extracted_data if s.get('category') == 'phrase']

        # Exibe palavras
        if words:
            preview_lines.append("🔤 PALAVRAS ISOLADAS (Short Strings/Stats):")
            preview_lines.append("-" * 50)
            for i, s in enumerate(words[:15]):
                confidence = s.get('confidence', 0)
                preview_lines.append(f"[{i+1:03d}] [{confidence:.2f}] {s['original']}")
            if len(words) > 15:
                preview_lines.append(f"... e mais {len(words) - 15} palavras")
            preview_lines.append("")

        # Exibe frases
        if phrases:
            preview_lines.append("💬 FRASES COMPLETAS (Long Strings/Dialogues):")
            preview_lines.append("-" * 50)
            for i, s in enumerate(phrases[:10]):
                confidence = s.get('confidence', 0)
                text = s['original']
                if len(text) > 60:
                    text = text[:57] + "..."
                preview_lines.append(f"[{i+1:03d}] [{confidence:.2f}] {text}")
            if len(phrases) > 10:
                preview_lines.append(f"... e mais {len(phrases) - 10} frases")

        self.preview_output.setPlainText('\n'.join(preview_lines))

    def cancel_extraction(self):
        """Cancela extração em andamento."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.log("⏹️ CANCELAMENTO SOLICITADO...")
        else:
            QMessageBox.information(self, "Aviso", "Nenhuma extração em andamento.")

    def export_json(self):
        """Exporta dados completos em JSON."""
        if not self.extracted_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado para exportar!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar JSON", "", "JSON Files (*.json)"
        )

        if file_path:
            export_data = {
                'metadata': {
                    'source_file': os.path.basename(self.rom_path),
                    'extraction_method': 'linguistic_heuristic',
                    'stats': self.linguistic_stats,
                    'total_strings': len(self.extracted_data)
                },
                'strings': self.extracted_data
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            self.log(f"💾 Exportado JSON: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Sucesso", f"JSON exportado:\n{file_path}")

    def export_txt(self):
        """Exporta apenas o texto original."""
        if not self.extracted_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado para exportar!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar TXT", "", "Text Files (*.txt)"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                for s in self.extracted_data:
                    category = s.get('category', 'unknown')
                    confidence = s.get('confidence', 0)
                    f.write(f"[{category.upper():8}] [{confidence:.3f}] {s['original']}\n")

            self.log(f"📄 Exportado TXT: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Sucesso", f"TXT exportado:\n{file_path}")

    def export_for_ai(self):
        """Exporta texto limpo para tradução por IA."""
        if not self.extracted_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado para exportar!")
            return

        # Filtra apenas textos de alta confiança
        high_confidence = [
            s for s in self.extracted_data
            if s.get('confidence', 0) >= 0.7 and len(s['original']) >= 3
        ]

        if not high_confidence:
            QMessageBox.warning(self, "Aviso", "Nenhum texto com confiança suficiente para IA!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar para IA", "", "Text Files (*.txt)"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=== TEXTO PARA TRADUÇÃO POR IA ===\n\n")
                f.write(f"Arquivo fonte: {os.path.basename(self.rom_path)}\n")
                f.write(f"Total de strings: {len(high_confidence)}\n")
                f.write("Extrator: Heurística Linguística\n")
                f.write("=" * 50 + "\n\n")

                for i, s in enumerate(high_confidence, 1):
                    text = s['original']
                    f.write(f"{i:03d}. {text}\n")

            self.log(f"🤖 Exportado para IA: {len(high_confidence)} textos limpos")
            QMessageBox.information(self, "Sucesso",
                f"✅ Exportação para IA concluída!\n\n"
                f"• {len(high_confidence)} textos de alta confiança\n"
                f"• Prontos para tradução por Gemini/Claude/GPT\n"
                f"• Arquivo: {file_path}")

    def log(self, message):
        """Adiciona mensagem ao log."""
        self.log_output.append(message)
        # Auto-scroll
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = ExtractionTab()
    window.setWindowTitle("Linguistic Extractor v2.0 - Heurística Humana")
    window.resize(900, 700)
    window.show()

    sys.exit(app.exec())
