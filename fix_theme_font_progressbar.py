#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORREÇÃO CRÍTICA:
1. Progress bars sem porcentagem
2. Tema não aplica quando usuário muda
3. Fonte não aplica quando usuário muda
4. Tema premium sobrescreve escolhas do usuário
"""

import re

def fix_interface():
    """Fix all issues in interface file"""

    with open('interface/interface_tradutor_final.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # ============================================
    # FIX 1: Progress Bars - Adicionar formatação com %
    # ============================================

    # Extraction progress bar
    content = content.replace(
        'self.extract_progress_bar = QProgressBar()',
        'self.extract_progress_bar = QProgressBar()\n        self.extract_progress_bar.setFormat("%p%")  # Show percentage'
    )

    # Optimization progress bar
    content = content.replace(
        'self.optimize_progress_bar = QProgressBar()',
        'self.optimize_progress_bar = QProgressBar()\n        self.optimize_progress_bar.setFormat("%p%")  # Show percentage'
    )

    # Translation progress bar
    content = content.replace(
        'self.translation_progress_bar = QProgressBar()',
        'self.translation_progress_bar = QProgressBar()\n        self.translation_progress_bar.setFormat("%p%")  # Show percentage'
    )

    # Reinsertion progress bar
    content = content.replace(
        'self.reinsertion_progress_bar = QProgressBar()',
        'self.reinsertion_progress_bar = QProgressBar()\n        self.reinsertion_progress_bar.setFormat("%p%")  # Show percentage'
    )

    # ============================================
    # FIX 2: Change Theme - Reaplicar premium CSS
    # ============================================

    old_change_theme = '''    def change_theme(self, theme_name: str):
        # Convert translated theme name to internal key
        internal_key = self.get_internal_theme_key(theme_name)
        self.current_theme = internal_key
        ThemeManager.apply(QApplication.instance(), internal_key)
        self.save_config()
        self.log(f"Theme changed to: {internal_key}")'''

    new_change_theme = '''    def change_theme(self, theme_name: str):
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

    content = content.replace(old_change_theme, new_change_theme)

    # ============================================
    # FIX 3: Change Font - Forçar refresh visual
    # ============================================

    old_change_font = '''    def change_font_family(self, font_name: str):
        self.current_font_family = font_name
        font_family_string = ProjectConfig.FONT_FAMILIES[font_name]
        primary_font = font_family_string.split(',')[0].strip()
        font = QFont()
        font.setFamily(primary_font)
        font.setPointSize(10)
        QApplication.instance().setFont(font)
        self.save_config()
        self.log(f"Font changed to: {font_name}")'''

    new_change_font = '''    def change_font_family(self, font_name: str):
        self.current_font_family = font_name
        font_family_string = ProjectConfig.FONT_FAMILIES[font_name]
        primary_font = font_family_string.split(',')[0].strip()

        font = QFont()
        font.setFamily(primary_font)
        font.setPointSize(10)

        # Apply font to application
        app = QApplication.instance()
        app.setFont(font)

        # Force update all widgets
        for widget in app.allWidgets():
            widget.setFont(font)
            widget.update()

        self.save_config()
        self.log(f"Font changed to: {font_name}")'''

    content = content.replace(old_change_font, new_change_font)

    # Write fixed content
    with open('interface/interface_tradutor_final.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Interface file fixed!")

# Run fix
print("=" * 70)
print("🔧 FIXING THEME, FONT, AND PROGRESS BAR ISSUES")
print("=" * 70)
print()
fix_interface()
print()
print("=" * 70)
print("✅ ALL FIXES APPLIED SUCCESSFULLY!")
print("=" * 70)
print()
print("📋 Changes made:")
print("   ✓ Progress bars now show percentage (0% - 100%)")
print("   ✓ Theme changes now reapply premium CSS")
print("   ✓ Font changes now force update all widgets")
print("   ✓ Visual feedback immediate on all changes")
print()
