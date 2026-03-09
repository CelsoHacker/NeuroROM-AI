# -*- coding: utf-8 -*-
"""
ENGINE RETRO-A - TEST LAUNCHER
Teste rápido das abas de Extração e Reinserção
"""
import sys
from PyQt6.QtWidgets import QApplication, QTabWidget

sys.path.insert(0, 'interface')
from gui_tabs import ExtractionTab, ReinsertionTab, GraphicLabTab

if __name__ == '__main__':
    app = QApplication(sys.argv)

    tabs = QTabWidget()
    tabs.setWindowTitle("ENGINE RETRO-A - Professional Translation Framework")
    tabs.setMinimumSize(1000, 700)

    # Adiciona abas
    tabs.addTab(ExtractionTab(), "📄 Extração")
    tabs.addTab(ReinsertionTab(), "💉 Reinserção")
    tabs.addTab(GraphicLabTab(), "🎨 Laboratório Gráfico")

    tabs.show()
    sys.exit(app.exec())
