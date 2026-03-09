#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORREÇÃO COMPLETA DA UI - PyQt6
Remove estilos hardcoded, corrige layouts, restaura sistema de temas
"""

import re

def fix_ui_complete():
    """Corrige todos os problemas de layout e temas da UI"""

    with open('interface/interface_tradutor_final.py', 'r', encoding='utf-8') as f:
        content = f.read()

    print("🔧 Iniciando correção da UI...")

    # ============================================
    # FIX 1: REMOVER IMPORTAÇÃO DO PREMIUM THEME
    # ============================================
    print("   ✓ Removendo premium theme (causando conflitos)...")

    # Remove as importações do premium theme
    content = re.sub(
        r'\s*try:\s*from interface\.premium_theme.*?import apply_premium_theme\s*apply_premium_theme\(.*?\)\s*except ImportError:\s*pass',
        '',
        content,
        flags=re.DOTALL
    )

    # ============================================
    # FIX 2: ADICIONAR ALTURAS MÍNIMAS NOS BOTÕES
    # ============================================
    print("   ✓ Adicionando alturas mínimas nos botões principais...")

    # Botão Extrair Dados
    content = content.replace(
        'self.extract_btn = QPushButton(self.tr("extract_data"))',
        'self.extract_btn = QPushButton(self.tr("extract_data"))\n        self.extract_btn.setMinimumHeight(50)'
    )

    # Botão Otimizar
    content = content.replace(
        'self.optimize_btn = QPushButton(self.tr("optimize_data"))',
        'self.optimize_btn = QPushButton(self.tr("optimize_data"))\n        self.optimize_btn.setMinimumHeight(50)'
    )

    # Botão Traduzir
    content = content.replace(
        'self.translate_btn = QPushButton(self.tr("translate"))',
        'self.translate_btn = QPushButton(self.tr("translate"))\n        self.translate_btn.setMinimumHeight(50)'
    )

    # Botão Reinserir
    content = content.replace(
        'self.reinsert_btn = QPushButton(self.tr("reinsert"))',
        'self.reinsert_btn = QPushButton(self.tr("reinsert"))\n        self.reinsert_btn.setMinimumHeight(50)'
    )

    # Botão Reiniciar
    content = content.replace(
        'restart_btn = QPushButton(self.tr("restart"))',
        'restart_btn = QPushButton(self.tr("restart"))\n        restart_btn.setMinimumHeight(50)'
    )

    # Botão Sair
    content = content.replace(
        'exit_btn = QPushButton(self.tr("exit"))',
        'exit_btn = QPushButton(self.tr("exit"))\n        exit_btn.setMinimumHeight(45)'
    )

    # ============================================
    # FIX 3: REMOVER TAMANHO FIXO DAS PROGRESS BARS NO CÓDIGO
    # (O CSS do tema vai controlar isso)
    # ============================================
    print("   ✓ Ajustando progress bars...")

    # Manter apenas o setFormat, remover qualquer setFixedHeight
    content = re.sub(
        r'(self\.\w+_progress_bar)\.setFixedHeight\(\d+\)',
        r'# \1 height controlled by theme',
        content
    )

    # ============================================
    # FIX 4: GARANTIR MARGENS ADEQUADAS NOS LAYOUTS
    # ============================================
    print("   ✓ Adicionando margens nos GroupBoxes...")

    # Adicionar margens no layout de cada tab após criar o QVBoxLayout
    # Extraction tab
    old_extract_layout = '''def create_extraction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()'''

    new_extract_layout = '''def create_extraction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margens adequadas
        layout.setSpacing(15)  # Espaçamento entre elementos'''

    content = content.replace(old_extract_layout, new_extract_layout)

    # Translation tab
    old_trans_layout = '''def create_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()'''

    new_trans_layout = '''def create_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margens adequadas
        layout.setSpacing(15)  # Espaçamento entre elementos'''

    content = content.replace(old_trans_layout, new_trans_layout)

    # Reinsertion tab
    old_reinsert_layout = '''def create_reinsertion_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()'''

    new_reinsert_layout = '''def create_reinsertion_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margens adequadas
        layout.setSpacing(15)  # Espaçamento entre elementos'''

    content = content.replace(old_reinsert_layout, new_reinsert_layout)

    # Settings tab
    old_settings_layout = '''def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()'''

    new_settings_layout = '''def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margens adequadas
        layout.setSpacing(15)  # Espaçamento entre elementos'''

    content = content.replace(old_settings_layout, new_settings_layout)

    # ============================================
    # FIX 5: REMOVER addStretch() NO FINAL DOS LAYOUTS
    # (Isso estava empurrando conteúdo para cima)
    # ============================================
    print("   ✓ Removendo addStretch() problemáticos...")

    # Comentar os addStretch() no final dos layouts de tabs
    content = re.sub(
        r'(\s+)(layout\.addStretch\(\))\s*(\n\s+widget\.setLayout)',
        r'\1# \2 - Removido para evitar esmagamento\3',
        content
    )

    # ============================================
    # FIX 6: REMOVER CHAMADAS AO PREMIUM THEME NO MAIN
    # ============================================
    print("   ✓ Limpando função main()...")

    old_main = '''    # Apply base theme colors
    ThemeManager.apply(app, "Preto (Black)")

    # Apply premium visual enhancements
    try:
        from interface.premium_theme import apply_premium_theme
        apply_premium_theme(app)
    except ImportError:
        print("⚠️ Premium theme not found, using standard theme")

    window = MainWindow()'''

    new_main = '''    # Apply base theme (tema padrão será carregado do config)
    ThemeManager.apply(app, "Preto (Black)")

    window = MainWindow()'''

    content = content.replace(old_main, new_main)

    # ============================================
    # FIX 7: SIMPLIFICAR change_theme() - SEM PREMIUM CSS
    # ============================================
    print("   ✓ Simplificando change_theme()...")

    old_change_theme = '''    def change_theme(self, theme_name: str):
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key

        # Apply base theme colors
        ThemeManager.apply(QApplication.instance(), internal_key)

        # Reapply premium CSS styling on top
        try:
            from interface.premium_theme import apply_premium_theme
            apply_premium_theme(QApplication.instance())
        except ImportError:
            pass

        self.save_config()
        self.log(f"Theme changed to: {internal_key}")'''

    new_change_theme = '''    def change_theme(self, theme_name: str):
        """Muda o tema da interface (Preto/Cinza/Branco)"""
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key

        # Apply theme colors - ThemeManager handles everything
        ThemeManager.apply(QApplication.instance(), internal_key)

        self.save_config()
        self.log(f"Theme changed to: {internal_key}")'''

    content = content.replace(old_change_theme, new_change_theme)

    # Write fixed content
    with open('interface/interface_tradutor_final.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Interface corrigida!\n")

# ============================================
# CRIAR CSS MÍNIMO E LIMPO (SEM CORES FIXAS)
# ============================================
def create_minimal_css():
    """Cria CSS minimalista que não interfere com temas"""

    minimal_css = '''#!/usr/bin/env python3
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
'''

    with open('interface/minimal_theme.py', 'w', encoding='utf-8') as f:
        f.write(minimal_css)

    print("✅ Tema minimalista criado: interface/minimal_theme.py\n")

# ============================================
# EXECUTAR CORREÇÕES
# ============================================
print("=" * 70)
print("🔧 CORREÇÃO COMPLETA DA UI - PyQt6")
print("=" * 70)
print()

print("📋 Correções que serão aplicadas:")
print("   1. Remover premium_theme (cores hardcoded)")
print("   2. Adicionar alturas mínimas nos botões (50px)")
print("   3. Remover addStretch() problemáticos")
print("   4. Adicionar margens adequadas (20px)")
print("   5. Simplificar change_theme()")
print("   6. Criar CSS minimalista (apenas layout)")
print()

fix_ui_complete()
create_minimal_css()

print("=" * 70)
print("✅ CORREÇÃO COMPLETA!")
print("=" * 70)
print()
print("📋 O que mudou:")
print("   ✓ Premium theme removido (causava conflito)")
print("   ✓ Botões principais com altura de 50px")
print("   ✓ Layouts com margens de 20px")
print("   ✓ Espaçamento entre elementos de 15px")
print("   ✓ Sistema de temas limpo (Preto/Cinza/Branco)")
print("   ✓ AUTO-DETECTAR visível (sem addStretch empurrando)")
print()
print("🎨 Temas funcionam corretamente agora:")
print("   • Preto: Fundo escuro")
print("   • Cinza: Fundo médio")
print("   • Branco: Fundo claro")
print()
print("Teste o programa e veja a diferença!")
print()
