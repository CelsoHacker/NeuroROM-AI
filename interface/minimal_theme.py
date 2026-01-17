#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MINIMAL CSS - APENAS LAYOUT, SEM CORES FIXAS
As cores são controladas pelo ThemeManager (Preto/Cinza/Branco)
"""

MINIMAL_STYLESHEET = """
/* ============================================
   LAYOUT APENAS - SEM CORES DE FUNDO FIXAS
   ============================================ */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}

/* Group Boxes - Apenas bordas e espaçamento */
QGroupBox {
    border: 1px solid palette(mid);
    border-radius: 6px;
    margin-top: 12px;
    padding: 15px 10px 10px 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
}

/* Botões - Altura e padding apenas */
QPushButton {
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 35px;
}

QPushButton:hover {
    border: 2px solid palette(highlight);
}

/* Progress Bars - Altura adequada */
QProgressBar {
    border: 1px solid palette(mid);
    border-radius: 6px;
    min-height: 30px;
    text-align: center;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: palette(highlight);
    border-radius: 4px;
}

/* ComboBoxes - Altura adequada */
QComboBox {
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 8px 10px;
    min-height: 30px;
}

QComboBox:hover {
    border: 1px solid palette(highlight);
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

/* Line Edits e Text Edits */
QLineEdit, QTextEdit {
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 6px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid palette(highlight);
}

/* Scroll Bars - Estilo limpo */
QScrollBar:vertical {
    border: none;
    width: 12px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background-color: palette(mid);
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: palette(highlight);
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid palette(mid);
    border-radius: 4px;
}

QTabBar::tab {
    border: 1px solid palette(mid);
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 10px 15px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: palette(highlight);
}

QTabBar::tab:hover:!selected {
    border: 1px solid palette(highlight);
}

/* Spin Boxes */
QSpinBox {
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 6px;
}

QSpinBox:focus {
    border: 1px solid palette(highlight);
}

/* Check Boxes */
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid palette(mid);
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: palette(highlight);
}
"""

def apply_minimal_theme(app):
    """Aplica CSS mínimo que respeita o tema escolhido"""
    app.setStyleSheet(MINIMAL_STYLESHEET)
