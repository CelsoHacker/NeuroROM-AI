#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREMIUM THEME FIXED - Respeita escolha de tema do usuário
Preserva: Bordas verdes + Scrollbar verde + Layout bonito
Muda: Cores de fundo conforme tema selecionado
"""

# Premium CSS que RESPEITA as cores do tema
PREMIUM_STYLESHEET = """
/* ============================================
   IMPORTANTES: Não fixar cores de fundo!
   Usar as cores do tema (palette) do Qt
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* ============================================
   GROUP BOXES - Bordas verdes, fundo do tema
   ============================================ */

QGroupBox {
    border: 2px solid #4CAF50;  /* Verde - preservado! */
    border-radius: 8px;
    margin-top: 15px;
    padding: 20px 15px 15px 15px;
    /* NÃO fixar background - usa cor do tema! */
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    top: 5px;
    padding: 0 8px;
    color: #4CAF50;  /* Verde - preservado! */
    font-weight: bold;
    font-size: 11pt;
}

/* ============================================
   BUTTONS - Com gradiente mas respeitando tema
   ============================================ */

QPushButton {
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 11pt;
    min-height: 40px;  /* Aumentado de 35px */
}

/* Botões principais verdes */
QPushButton[objectName="extract_btn"],
QPushButton[objectName="translate_btn"],
QPushButton[objectName="restart_btn"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #4CAF50, stop:1 #45a049
    );
    color: white;
}

QPushButton[objectName="extract_btn"]:hover,
QPushButton[objectName="translate_btn"]:hover,
QPushButton[objectName="restart_btn"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #5CBF60, stop:1 #4CAF50
    );
}

/* Botão laranja (otimizar) */
QPushButton[objectName="optimize_btn"],
QPushButton[objectName="reinsert_btn"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF9800, stop:1 #e68900
    );
    color: white;
}

QPushButton[objectName="optimize_btn"]:hover,
QPushButton[objectName="reinsert_btn"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFA726, stop:1 #FF9800
    );
}

/* Botão preto (sair) */
QPushButton[objectName="exit_btn"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #333333, stop:1 #000000
    );
    color: #FFFFFF;
    border: 1px solid #555555;
}

/* Botões desabilitados */
QPushButton:disabled {
    background-color: #999999;
    color: #555555;
}

/* Botões secundários - usam cor do tema */
QPushButton[objectName="select_rom_btn"],
QPushButton[objectName="sel_file_btn"],
QPushButton[objectName="select_reinsert_rom_btn"],
QPushButton[objectName="select_translated_btn"] {
    border: 2px solid #4CAF50;  /* Borda verde */
    min-height: 35px;
    font-size: 10pt;
    border-radius: 6px;
}

QPushButton[objectName="select_rom_btn"]:hover,
QPushButton[objectName="sel_file_btn"]:hover,
QPushButton[objectName="select_reinsert_rom_btn"]:hover,
QPushButton[objectName="select_translated_btn"]:hover {
    border: 2px solid #66BB6A;  /* Borda verde mais clara */
    background-color: rgba(76, 175, 80, 0.1);  /* Verde transparente */
}

/* ============================================
   PROGRESS BARS - Altura adequada + gradiente verde
   ============================================ */

QProgressBar {
    border: 2px solid #4CAF50;  /* Borda verde */
    border-radius: 8px;
    height: 35px;  /* Altura fixa adequada */
    min-height: 35px;
    max-height: 35px;
    text-align: center;
    font-weight: bold;
    font-size: 11pt;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4CAF50, stop:0.5 #66BB6A, stop:1 #4CAF50
    );
    border-radius: 6px;
    margin: 2px;
}

/* ============================================
   COMBO BOXES - Bordas verdes, fundo do tema
   ============================================ */

QComboBox {
    border: 2px solid #4CAF50;  /* Borda verde */
    border-radius: 6px;
    padding: 10px 12px;  /* Aumentado padding */
    font-size: 10pt;
    min-height: 35px;  /* Altura mínima aumentada para melhor visibilidade */
}

QComboBox:hover {
    border: 2px solid #66BB6A;
}

QComboBox:focus {
    border: 2px solid #66BB6A;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #4CAF50;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    border: 2px solid #4CAF50;
    selection-background-color: #4CAF50;
    selection-color: white;
    outline: none;
    padding: 5px;
}

/* ============================================
   TEXT EDITS & LINE EDITS - Bordas verdes
   ============================================ */

QLineEdit, QTextEdit {
    border: 2px solid #4CAF50;
    border-radius: 6px;
    padding: 8px;
    font-size: 10pt;
}

QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #66BB6A;
}

/* ============================================
   LABELS - Sem fundo fixo
   ============================================ */

QLabel[objectName="rom_path_label"],
QLabel[objectName="trans_file_label"],
QLabel[objectName="reinsert_rom_label"],
QLabel[objectName="translated_file_label"] {
    padding: 10px 12px;
    border: 2px solid #4CAF50;
    border-radius: 6px;
    font-size: 10pt;
}

QLabel[objectName="extract_status_label"],
QLabel[objectName="optimize_status_label"],
QLabel[objectName="translation_status_label"],
QLabel[objectName="reinsertion_status_label"] {
    padding: 10px;
    font-weight: bold;
    font-size: 11pt;
}

/* ============================================
   TAB WIDGET - Abas com verde
   ============================================ */

QTabWidget::pane {
    border: 2px solid #4CAF50;
    border-radius: 8px;
    padding: 10px;
}

QTabBar::tab {
    border: 2px solid #4CAF50;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 12px 20px;
    margin-right: 5px;
    font-weight: bold;
    font-size: 11pt;
}

QTabBar::tab:selected {
    background: #4CAF50;
    color: white;
}

QTabBar::tab:hover:!selected {
    border: 2px solid #66BB6A;
}

/* ============================================
   SCROLL BARS - Verde preservado!
   ============================================ */

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 14px;
    border-radius: 7px;
}

QScrollBar::handle:vertical {
    background-color: #4CAF50;  /* Verde - preservado! */
    border-radius: 7px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #66BB6A;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 14px;
    border-radius: 7px;
}

QScrollBar::handle:horizontal {
    background-color: #4CAF50;
    border-radius: 7px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #66BB6A;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ============================================
   SPIN BOXES - Bordas verdes
   ============================================ */

QSpinBox {
    border: 2px solid #4CAF50;
    border-radius: 6px;
    padding: 8px;
    font-size: 10pt;
    min-height: 25px;
}

QSpinBox:focus {
    border: 2px solid #66BB6A;
}

QSpinBox::up-button, QSpinBox::down-button {
    border: none;
    width: 20px;
    border-radius: 4px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #4CAF50;
}

/* ============================================
   CHECKBOXES - Verde
   ============================================ */

QCheckBox {
    spacing: 8px;
    font-size: 10pt;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #4CAF50;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
}

QCheckBox::indicator:hover {
    border: 2px solid #66BB6A;
}

/* ============================================
   STATUS BAR - Verde
   ============================================ */

QStatusBar {
    color: #4CAF50;
    border-top: 2px solid #4CAF50;
    padding: 5px;
    font-weight: bold;
}
"""

def apply_premium_theme(app):
    """Aplica tema premium que respeita cores do tema escolhido"""
    app.setStyleSheet(PREMIUM_STYLESHEET)
