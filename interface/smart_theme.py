#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMART THEME SYSTEM - Bordas com Contraste Dinâmico
Muda bordas e fundos de acordo com o tema ativo (Preto/Cinza/Branco)
"""

# ============================================
# TEMA ESCURO (PRETO) - Bordas Claras
# ============================================
DARK_THEME_STYLE = """
/* ============================================
   TEMA ESCURO - Bordas com Contraste
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* GROUP BOXES - Bordas visíveis em fundo escuro */
QGroupBox {
    border: 1px solid #555555;  /* Cinza médio - visível em fundo escuro */
    border-radius: 6px;
    margin-top: 20px;  /* Espaço para o título */
    padding: 20px 10px 10px 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 5px;
    padding: 0 5px;
}

/* INPUTS - Fundo ligeiramente mais claro que janela */
QLineEdit, QTextEdit {
    border: 1px solid #4D4D4D;  /* Borda cinza médio */
    border-radius: 4px;
    padding: 6px;
    background-color: #1E1E1E;  /* Mais claro que fundo #121212 */
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #6D6D6D;  /* Borda mais clara no foco */
}

/* COMBO BOXES - Bordas visíveis */
QComboBox {
    border: 1px solid #4D4D4D;
    border-radius: 4px;
    padding: 8px 10px;
    background-color: #1E1E1E;
    min-height: 35px;
}

QComboBox:hover {
    border: 1px solid #6D6D6D;
}

QComboBox:focus {
    border: 1px solid #6D6D6D;
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

QComboBox QAbstractItemView {
    border: 1px solid #4D4D4D;
    background-color: #1E1E1E;
    selection-background-color: #3D3D3D;
}

/* BUTTONS - Bordas sutis */
QPushButton {
    border: 1px solid #4D4D4D;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 35px;
    background-color: #2D2D2D;
}

QPushButton:hover {
    border: 1px solid #6D6D6D;
    background-color: #3D3D3D;
}

QPushButton:pressed {
    background-color: #1D1D1D;
}

/* PROGRESS BARS - Bordas visíveis */
QProgressBar {
    border: 1px solid #4D4D4D;
    border-radius: 6px;
    min-height: 30px;
    text-align: center;
    font-weight: bold;
    background-color: #0D0D0D;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 4px;
}

/* SPIN BOXES */
QSpinBox {
    border: 1px solid #4D4D4D;
    border-radius: 4px;
    padding: 6px;
    background-color: #1E1E1E;
}

QSpinBox:focus {
    border: 1px solid #6D6D6D;
}

/* CHECKBOXES */
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #4D4D4D;
    border-radius: 3px;
    background-color: #1E1E1E;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
}

/* TABS */
QTabWidget::pane {
    border: 1px solid #4D4D4D;
    border-radius: 4px;
}

QTabBar::tab {
    border: 1px solid #4D4D4D;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 10px 15px;
    margin-right: 2px;
    background-color: #2D2D2D;
}

QTabBar::tab:selected {
    background-color: #3D3D3D;
}

QTabBar::tab:hover:!selected {
    border: 1px solid #6D6D6D;
}

/* SCROLL BARS */
QScrollBar:vertical {
    border: none;
    width: 12px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background-color: #4D4D4D;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6D6D6D;
}

QScrollBar:horizontal {
    border: none;
    height: 12px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background-color: #4D4D4D;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #6D6D6D;
}
"""

# ============================================
# TEMA CINZA - Bordas Médias
# ============================================
GRAY_THEME_STYLE = """
/* ============================================
   TEMA CINZA - Bordas Balanceadas
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* GROUP BOXES */
QGroupBox {
    border: 1px solid #999999;  /* Cinza médio */
    border-radius: 6px;
    margin-top: 20px;
    padding: 20px 10px 10px 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 5px;
    padding: 0 5px;
}

/* INPUTS */
QLineEdit, QTextEdit {
    border: 1px solid #999999;
    border-radius: 4px;
    padding: 6px;
    background-color: #E5E5E5;  /* Ligeiramente mais claro */
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #666666;
}

/* COMBO BOXES */
QComboBox {
    border: 1px solid #999999;
    border-radius: 4px;
    padding: 8px 10px;
    background-color: #E5E5E5;
    min-height: 35px;
}

QComboBox:hover {
    border: 1px solid #666666;
}

QComboBox:focus {
    border: 1px solid #666666;
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

QComboBox QAbstractItemView {
    border: 1px solid #999999;
    background-color: #E5E5E5;
    selection-background-color: #CCCCCC;
}

/* BUTTONS */
QPushButton {
    border: 1px solid #999999;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 35px;
    background-color: #D0D0D0;
}

QPushButton:hover {
    border: 1px solid #666666;
    background-color: #E0E0E0;
}

QPushButton:pressed {
    background-color: #C0C0C0;
}

/* PROGRESS BARS */
QProgressBar {
    border: 1px solid #999999;
    border-radius: 6px;
    min-height: 30px;
    text-align: center;
    font-weight: bold;
    background-color: #CCCCCC;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 4px;
}

/* SPIN BOXES */
QSpinBox {
    border: 1px solid #999999;
    border-radius: 4px;
    padding: 6px;
    background-color: #E5E5E5;
}

QSpinBox:focus {
    border: 1px solid #666666;
}

/* CHECKBOXES */
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #999999;
    border-radius: 3px;
    background-color: #E5E5E5;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
}

/* TABS */
QTabWidget::pane {
    border: 1px solid #999999;
    border-radius: 4px;
}

QTabBar::tab {
    border: 1px solid #999999;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 10px 15px;
    margin-right: 2px;
    background-color: #D0D0D0;
}

QTabBar::tab:selected {
    background-color: #E5E5E5;
}

QTabBar::tab:hover:!selected {
    border: 1px solid #666666;
}

/* SCROLL BARS */
QScrollBar:vertical {
    border: none;
    width: 12px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background-color: #999999;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #666666;
}

QScrollBar:horizontal {
    border: none;
    height: 12px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background-color: #999999;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #666666;
}
"""

# ============================================
# TEMA CLARO (BRANCO) - Bordas Escuras
# ============================================
LIGHT_THEME_STYLE = """
/* ============================================
   TEMA CLARO - Bordas Escuras
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* GROUP BOXES */
QGroupBox {
    border: 1px solid #CCCCCC;  /* Cinza claro em fundo branco */
    border-radius: 6px;
    margin-top: 20px;
    padding: 20px 10px 10px 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 5px;
    padding: 0 5px;
}

/* INPUTS */
QLineEdit, QTextEdit {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    padding: 6px;
    background-color: #FAFAFA;  /* Ligeiramente mais escuro que branco puro */
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #999999;
}

/* COMBO BOXES */
QComboBox {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    padding: 8px 10px;
    background-color: #FAFAFA;
    min-height: 35px;
}

QComboBox:hover {
    border: 1px solid #999999;
}

QComboBox:focus {
    border: 1px solid #999999;
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

QComboBox QAbstractItemView {
    border: 1px solid #CCCCCC;
    background-color: #FAFAFA;
    selection-background-color: #E0E0E0;
}

/* BUTTONS */
QPushButton {
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 35px;
    background-color: #F0F0F0;
}

QPushButton:hover {
    border: 1px solid #999999;
    background-color: #E5E5E5;
}

QPushButton:pressed {
    background-color: #D8D8D8;
}

/* PROGRESS BARS */
QProgressBar {
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    min-height: 30px;
    text-align: center;
    font-weight: bold;
    background-color: #F5F5F5;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 4px;
}

/* SPIN BOXES */
QSpinBox {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    padding: 6px;
    background-color: #FAFAFA;
}

QSpinBox:focus {
    border: 1px solid #999999;
}

/* CHECKBOXES */
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #CCCCCC;
    border-radius: 3px;
    background-color: #FAFAFA;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
}

/* TABS */
QTabWidget::pane {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
}

QTabBar::tab {
    border: 1px solid #CCCCCC;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 10px 15px;
    margin-right: 2px;
    background-color: #F0F0F0;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
}

QTabBar::tab:hover:!selected {
    border: 1px solid #999999;
}

/* SCROLL BARS */
QScrollBar:vertical {
    border: none;
    width: 12px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background-color: #CCCCCC;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #999999;
}

QScrollBar:horizontal {
    border: none;
    height: 12px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background-color: #CCCCCC;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #999999;
}
"""

# ============================================
# FUNÇÃO DE APLICAÇÃO INTELIGENTE
# ============================================
def apply_smart_theme(app, theme_name: str):
    """
    Aplica o tema correto com bordas contrastantes

    Args:
        app: QApplication instance
        theme_name: "Preto (Black)", "Cinza (Gray)", ou "Branco (White)"
    """
    # Normalizar nome do tema
    theme_lower = theme_name.lower()

    if "preto" in theme_lower or "black" in theme_lower:
        # Tema Escuro - Bordas claras (#4D4D4D)
        app.setStyleSheet(DARK_THEME_STYLE)
    elif "cinza" in theme_lower or "gray" in theme_lower or "grey" in theme_lower:
        # Tema Cinza - Bordas médias (#999999)
        app.setStyleSheet(GRAY_THEME_STYLE)
    elif "branco" in theme_lower or "white" in theme_lower:
        # Tema Claro - Bordas escuras (#CCCCCC)
        app.setStyleSheet(LIGHT_THEME_STYLE)
    else:
        # Fallback para tema escuro
        app.setStyleSheet(DARK_THEME_STYLE)
