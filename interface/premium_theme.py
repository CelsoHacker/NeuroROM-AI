#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREMIUM VISUAL THEME FOR NEUROROM AI
Melhorias profissionais para interface comercial de alto nível
"""

# Premium CSS Stylesheet para PyQt6
PREMIUM_STYLESHEET = """
/* ============================================
   GLOBAL SETTINGS - Melhorias gerais
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* ============================================
   GROUP BOXES - Containers modernos
   ============================================ */

QGroupBox {
    border: 2px solid #2d2d2d;
    border-radius: 8px;
    margin-top: 15px;
    padding: 20px 15px 15px 15px;
    background-color: #1a1a1a;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    top: 5px;
    padding: 0 8px;
    color: #4CAF50;
    font-weight: bold;
    font-size: 11pt;
    background-color: #1a1a1a;
}

/* ============================================
   BUTTONS - Botões com profundidade e animação
   ============================================ */

QPushButton {
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 11pt;
    min-height: 35px;
}

/* Botões primários verdes */
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

QPushButton[objectName="extract_btn"]:pressed,
QPushButton[objectName="translate_btn"]:pressed,
QPushButton[objectName="restart_btn"]:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #3d8b40, stop:1 #388e3c
    );
}

/* Botão laranja (otimizar) */
QPushButton[objectName="optimize_btn"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF9800, stop:1 #e68900
    );
    color: white;
}

QPushButton[objectName="optimize_btn"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFA726, stop:1 #FF9800
    );
}

/* Botão preto (sair) */
QPushButton[objectName="exit_btn"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a1a, stop:1 #000000
    );
    color: #FFFFFF;
    border: 1px solid #333333;
}

QPushButton[objectName="exit_btn"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #2d2d2d, stop:1 #1a1a1a
    );
}

/* Botões desabilitados */
QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
    border: 1px solid #999999;
}

/* Botões secundários (select file, select ROM) */
QPushButton[objectName="select_rom_btn"],
QPushButton[objectName="sel_file_btn"],
QPushButton[objectName="select_reinsert_rom_btn"],
QPushButton[objectName="select_translated_btn"] {
    background-color: #2d2d2d;
    color: #FFFFFF;
    border: 1px solid #444444;
    min-height: 30px;
    font-size: 10pt;
}

QPushButton[objectName="select_rom_btn"]:hover,
QPushButton[objectName="sel_file_btn"]:hover,
QPushButton[objectName="select_reinsert_rom_btn"]:hover,
QPushButton[objectName="select_translated_btn"]:hover {
    background-color: #3d3d3d;
    border: 1px solid #4CAF50;
}

/* ============================================
   PROGRESS BARS - Barras com gradiente
   ============================================ */

QProgressBar {
    border: 2px solid #2d2d2d;
    border-radius: 8px;
    background-color: #0d0d0d;
    height: 35px;
    min-height: 35px;
    max-height: 35px;
    text-align: center;
    color: white;
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
   COMBO BOXES - Dropdowns modernos
   ============================================ */

QComboBox {
    border: 2px solid #2d2d2d;
    border-radius: 6px;
    padding: 10px 12px;
    background-color: #1a1a1a;
    color: white;
    font-size: 10pt;
    min-height: 35px;
}

QComboBox:hover {
    border: 2px solid #4CAF50;
}

QComboBox:focus {
    border: 2px solid #4CAF50;
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
    background-color: #1a1a1a;
    color: white;
    selection-background-color: #4CAF50;
    selection-color: white;
    outline: none;
}

/* ============================================
   TEXT EDITS & LINE EDITS - Campos de texto
   ============================================ */

QLineEdit, QTextEdit {
    border: 2px solid #2d2d2d;
    border-radius: 6px;
    padding: 8px;
    background-color: #1a1a1a;
    color: white;
    font-size: 10pt;
}

QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #4CAF50;
}

QTextEdit {
    padding: 10px;
}

/* ============================================
   LABELS - Rótulos especiais
   ============================================ */

QLabel[objectName="rom_path_label"],
QLabel[objectName="trans_file_label"],
QLabel[objectName="reinsert_rom_label"],
QLabel[objectName="translated_file_label"] {
    padding: 8px 12px;
    background-color: #1a1a1a;
    border: 2px solid #2d2d2d;
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
   TAB WIDGET - Sistema de abas moderno
   ============================================ */

QTabWidget::pane {
    border: 2px solid #2d2d2d;
    border-radius: 8px;
    background-color: #0d0d0d;
    padding: 10px;
}

QTabBar::tab {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #2d2d2d, stop:1 #1a1a1a
    );
    border: 2px solid #2d2d2d;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 12px 20px;
    margin-right: 5px;
    color: #CCCCCC;
    font-weight: bold;
    font-size: 11pt;
}

QTabBar::tab:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #4CAF50, stop:1 #45a049
    );
    color: white;
    border: 2px solid #4CAF50;
    border-bottom: none;
}

QTabBar::tab:hover:!selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #3d3d3d, stop:1 #2d2d2d
    );
}

/* ============================================
   SCROLL BARS - Barras de rolagem modernas
   ============================================ */

QScrollBar:vertical {
    border: none;
    background-color: #0d0d0d;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #4CAF50;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #66BB6A;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ============================================
   SPIN BOXES - Campos numéricos
   ============================================ */

QSpinBox {
    border: 2px solid #2d2d2d;
    border-radius: 6px;
    padding: 8px;
    background-color: #1a1a1a;
    color: white;
    font-size: 10pt;
}

QSpinBox:focus {
    border: 2px solid #4CAF50;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #2d2d2d;
    border: none;
    width: 20px;
    border-radius: 4px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #4CAF50;
}

/* ============================================
   CHECKBOXES - Caixas de seleção
   ============================================ */

QCheckBox {
    spacing: 8px;
    color: white;
    font-size: 10pt;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #2d2d2d;
    border-radius: 4px;
    background-color: #1a1a1a;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
    border: 2px solid #4CAF50;
}

QCheckBox::indicator:hover {
    border: 2px solid #4CAF50;
}

/* ============================================
   STATUS BAR - Barra de status
   ============================================ */

QStatusBar {
    background-color: #0d0d0d;
    color: #4CAF50;
    border-top: 2px solid #2d2d2d;
    padding: 5px;
    font-weight: bold;
}

/* ============================================
   MESSAGE BOX - Diálogos
   ============================================ */

QMessageBox {
    background-color: #0d0d0d;
}

QMessageBox QLabel {
    color: white;
    font-size: 10pt;
}

QMessageBox QPushButton {
    min-width: 80px;
    min-height: 30px;
}
"""

def apply_premium_theme(app):
    """Aplica o tema premium na aplicação"""
    app.setStyleSheet(PREMIUM_STYLESHEET)
    print("✅ Premium Theme Applied Successfully!")
