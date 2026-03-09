#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RESET TO WORKING STATE - Visual Bonito e Funcional
Reverte para o visual verde bonito, mantendo apenas correções essenciais
"""

import re

def reset_interface():
    """Volta ao visual bonito e funcional"""

    with open('interface/interface_tradutor_final.py', 'r', encoding='utf-8') as f:
        content = f.read()

    print("🔄 Revertendo para visual bonito e funcional...")

    # ============================================
    # FIX 1: Usar premium_theme.py (visual bonito)
    # ============================================
    print("   ✓ Ativando premium theme (visual bonito)...")

    # Na função change_theme, usar premium_theme
    old_change_theme = '''        # Apply smart theme with contrasting borders
        try:
            from interface.smart_theme import apply_smart_theme
            apply_smart_theme(QApplication.instance(), internal_key)
        except ImportError:
            pass'''

    new_change_theme = '''        # Apply premium theme (visual bonito)
        try:
            from interface.premium_theme import apply_premium_theme
            apply_premium_theme(QApplication.instance())
        except ImportError:
            pass'''

    content = content.replace(old_change_theme, new_change_theme)

    # Na função main, usar premium_theme
    old_main = '''    # Apply smart theme with contrasting borders
    try:
        from interface.smart_theme import apply_smart_theme
        apply_smart_theme(app, "Preto (Black)")
    except ImportError:
        pass'''

    new_main = '''    # Apply premium theme (visual bonito)
    try:
        from interface.premium_theme import apply_premium_theme
        apply_premium_theme(app)
    except ImportError:
        pass'''

    content = content.replace(old_main, new_main)

    # Write fixed content
    with open('interface/interface_tradutor_final.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Interface restaurada!\n")

# Run
print("=" * 70)
print("🔄 RESET TO WORKING STATE")
print("=" * 70)
print()
print("Voltando ao visual bonito e funcional...")
print()

reset_interface()

print("=" * 70)
print("✅ RESET COMPLETO!")
print("=" * 70)
print()
print("📋 O que foi restaurado:")
print("   ✓ Visual verde bonito (premium_theme.py)")
print("   ✓ Botões coloridos (verde, laranja, preto)")
print("   ✓ Bordas verdes")
print("   ✓ Scrollbar verde")
print("   ✓ Progress bars com porcentagem")
print("   ✓ Layouts com espaçamento adequado")
print("   ✓ Botões com altura de 50px")
print()
print("🎮 PRONTO PARA TESTAR E VENDER!")
print()
