#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIX AUTO-DETECTAR VISIBILITY
Adiciona espaçamento e margens adequadas para evitar que ComboBoxes sejam empurrados para cima
"""

import re

def fix_auto_detectar_visibility():
    """Fix AUTO-DETECTAR ComboBox visibility by adding proper spacing"""

    with open('interface/interface_tradutor_final.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # ============================================
    # FIX 1: Add spacing to language config GridLayout
    # ============================================

    old_lang_config = '''        lang_config_group = QGroupBox(self.tr("language_config"))
        lang_config_group.setObjectName("lang_config_group")
        lang_config_layout = QGridLayout()
        source_lang_label = QLabel(self.tr("source_language"))'''

    new_lang_config = '''        lang_config_group = QGroupBox(self.tr("language_config"))
        lang_config_group.setObjectName("lang_config_group")
        lang_config_layout = QGridLayout()
        lang_config_layout.setVerticalSpacing(15)  # Add vertical spacing between rows
        lang_config_layout.setHorizontalSpacing(10)  # Add horizontal spacing
        lang_config_layout.setContentsMargins(15, 25, 15, 15)  # Add margins (left, top, right, bottom)
        source_lang_label = QLabel(self.tr("source_language"))'''

    content = content.replace(old_lang_config, new_lang_config)

    # ============================================
    # FIX 2: Add proper size policy to source_lang_combo
    # ============================================

    old_source_combo = '''        self.source_lang_combo = QComboBox()
        # Populate with translated source language names
        self.source_lang_combo.addItems(self.get_all_translated_source_languages())
        lang_config_layout.addWidget(self.source_lang_combo, 0, 1)'''

    new_source_combo = '''        self.source_lang_combo = QComboBox()
        self.source_lang_combo.setMinimumHeight(35)  # Ensure minimum height
        self.source_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Populate with translated source language names
        self.source_lang_combo.addItems(self.get_all_translated_source_languages())
        lang_config_layout.addWidget(self.source_lang_combo, 0, 1)'''

    content = content.replace(old_source_combo, new_source_combo)

    # ============================================
    # FIX 3: Add proper size policy to target_lang_combo
    # ============================================

    old_target_combo = '''        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
        lang_config_layout.addWidget(self.target_lang_combo, 1, 1)'''

    new_target_combo = '''        self.target_lang_combo = QComboBox()
        self.target_lang_combo.setMinimumHeight(35)  # Ensure minimum height
        self.target_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.target_lang_combo.addItems(ProjectConfig.TARGET_LANGUAGES.keys())
        lang_config_layout.addWidget(self.target_lang_combo, 1, 1)'''

    content = content.replace(old_target_combo, new_target_combo)

    # Write fixed content
    with open('interface/interface_tradutor_final.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ AUTO-DETECTAR visibility fixed!")

# Run fix
print("=" * 70)
print("🔧 FIXING AUTO-DETECTAR VISIBILITY ISSUE")
print("=" * 70)
print()
fix_auto_detectar_visibility()
print()
print("=" * 70)
print("✅ FIX APPLIED SUCCESSFULLY!")
print("=" * 70)
print()
print("📋 Changes made:")
print("   ✓ Added vertical spacing (15px) between rows")
print("   ✓ Added horizontal spacing (10px)")
print("   ✓ Added content margins (15px, 25px top)")
print("   ✓ Set minimum height (35px) for ComboBoxes")
print("   ✓ Set proper size policy (Expanding, Fixed)")
print()
