#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar todos os arquivos de tradução i18n automaticamente
Execute: python generate_translations.py
"""

import json
from pathlib import Path

# Diretório de saída
I18N_DIR = Path(__file__).parent / "i18n"
I18N_DIR.mkdir(exist_ok=True)

# Template base para todas as traduções
def create_translation(lang_code, lang_name, translations):
    return {
        "_meta": {"language": lang_name, "code": lang_code, "version": "1.0.0"},
        **translations
    }

# Traduções para cada idioma (chaves principais)
translations_data = {
    "fr": {
        "name": "Français (France)",
        "title": "Extraction - Optimisation - Traduction IA - Réinsertion",
        "tab1": "🔍 1. Extraction", "tab2": "🧠 2. Traduction", "tab3": "📥 3. Réinsertion", "tab4": "⚙️ Paramètres",
        "platform": "Plateforme:",
        "platform_snes": "Super Nintendo (SNES)", "platform_ps1": "PlayStation 1 (PS1)", "platform_pc": "Jeux PC (Windows)",
        "platform_nes": "🚧 Nintendo Entertainment System (NES) - En phase de test",
        "platform_gba": "🚧 Game Boy Advance (GBA) - En phase de test",
        "platform_nds": "🚧 Nintendo DS (NDS) - En phase de test",
        "platform_n64": "🚧 Nintendo 64 (N64) - En phase de test",
        "platform_ps2": "🚧 PlayStation 2 (PS2) - En phase de test",
        "platform_ps3": "🚧 PlayStation 3 (PS3) - En phase de test",
        "platform_md": "🚧 Sega Mega Drive - En phase de test",
        "platform_sms": "🚧 Sega Master System - En phase de test",
        "platform_dc": "�� Sega Dreamcast - En phase de test",
        "platform_xbox": "🚧 Xbox - En phase de test",
        "platform_x360": "🚧 Xbox 360 - En phase de test",
        "platform_roadmap": "📋 Voir Plateformes en Développement...",
        "platform_in_development": "Plateforme en développement",
        "separator": "──────────────────────",
        "rom_file": "📂 Fichier ROM", "no_rom": "⚠️ Aucune ROM sélectionnée", "select_rom": "📂 Sélectionner ROM",
        "extract_texts": "📄 Extraire Textes", "optimize_data": "🧹 Optimiser Données",
        "extraction_progress": "Progrès d'Extraction", "optimization_progress": "Progrès d'Optimisation",
        "waiting": "En attente de démarrage...", "language_config": "🌍 Configuration Linguistique",
        "source_language": "📖 Langue Source (ROM)", "target_language": "🎯 Langue Cible",
        "translation_mode": "Mode de Traduction", "api_config": "Configuration API",
        "api_key": "Clé API:", "workers": "Workers:", "timeout": "Timeout (s):",
        "use_cache": "Utiliser cache de traductions", "translation_progress": "Progrès de Traduction",
        "translate_ai": "🤖 Traduire avec IA", "stop_translation": "🛑 Arrêter Traduction",
        "original_rom": "📂 ROM Originale", "translated_file": "📄 Fichier Traduit",
        "select_file": "📄 Sélectionner Fichier", "output_rom": "💾 ROM Traduite (Sortie)",
        "reinsertion_progress": "Progrès de Réinsertion", "reinsert": "Réinsérer Traduction",
        "theme": "🎨 Thème Visuel", "ui_language": "🌐 Langue de l'Interface", "font_family": "🔤 Police de l'Interface",
        "log": "Journal des Opérations", "restart": "Redémarrer", "exit": "Quitter",
        "developer": "Développé par: Celso (Développeur Solo)", "in_dev": "EN DÉVELOPPEMENT",
        "file_to_translate": "📄 Fichier à Traduire (Optimisé)", "no_file": "📄 Aucun fichier sélectionné",
        "help_support": "🆘 Aide et Support", "manual_guide": "📘 Guide d'Utilisation Professionnel:",
        "manual_guide_title": "📘 Guide d'Utilisation Professionnel",
        "manual_step_1": "Étape 1: Extraction", "manual_step_2": "Étape 2: Optimisation",
        "manual_step_3": "Étape 3: Traduction", "manual_step_4": "Étape 4: Réinsertion",
        "manual_step_1_title": "📖 Étape 1: Extraction de Textes",
        "manual_step_2_title": "📖 Étape 2: Optimisation des Données",
        "manual_step_3_title": "📖 Étape 3: Traduction avec IA",
        "manual_step_4_title": "📖 Étape 4: Réinsertion dans la ROM",
        "manual_step_1_content": "<h2>🎯 Objectif</h2><p>Extraire tous les textes traduisibles de la ROM ou jeu PC.</p>",
        "manual_step_2_content": "<h2>🎯 Objectif</h2><p>Supprimer les doublons et les déchets binaires pour économiser jusqu'à 80% sur les appels API.</p>",
        "manual_step_3_content": "<h2>🎯 Objectif</h2><p>Traduire les textes optimisés en utilisant l'IA (Gemini ou Ollama).</p>",
        "manual_step_4_content": "<h2>🎯 Objectif</h2><p>Réinsérer les textes traduits dans la ROM originale.</p>",
        "btn_stop": "Arrêter Traduction", "btn_close": "Fermer",
        "roadmap_item": "Prochaines Consoles (Roadmap)...", "roadmap_title": "Roadmap",
        "roadmap_desc": "Plateformes en développement:", "roadmap_header": "Plateformes en Développement",
        "roadmap_description": "Ces plateformes seront ajoutées dans les futures mises à jour:",
        "roadmap_note": "Note: Les mises à jour sont gratuites pour les acheteurs du framework.",
        "roadmap_cat_playstation": "PlayStation", "roadmap_cat_nintendo_classic": "Nintendo Classic",
        "roadmap_cat_nintendo_portable": "Nintendo Portable",
        "roadmap_cat_sega": "Sega", "roadmap_cat_xbox": "Xbox", "roadmap_cat_other": "Autre"
    },
    "de": {
        "name": "Deutsch (Deutschland)",
        "title": "Extraktion - Optimierung - KI-Übersetzung - Wiedereinf

ügung",
        "tab1": "🔍 1. Extraktion", "tab2": "🧠 2. Übersetzung", "tab3": "📥 3. Wiedereinfügung", "tab4": "⚙️ Einstellungen",
        "platform": "Plattform:",
        "platform_snes": "Super Nintendo (SNES)", "platform_ps1": "PlayStation 1 (PS1)", "platform_pc": "PC-Spiele (Windows)",
        "platform_nes": "🚧 Nintendo Entertainment System (NES) - In Testphase",
        "platform_gba": "🚧 Game Boy Advance (GBA) - In Testphase",
        "platform_nds": "🚧 Nintendo DS (NDS) - In Testphase",
        "platform_n64": "🚧 Nintendo 64 (N64) - In Testphase",
        "platform_ps2": "🚧 PlayStation 2 (PS2) - In Testphase",
        "platform_ps3": "🚧 PlayStation 3 (PS3) - In Testphase",
        "platform_md": "🚧 Sega Mega Drive - In Testphase",
        "platform_sms": "🚧 Sega Master System - In Testphase",
        "platform_dc": "🚧 Sega Dreamcast - In Testphase",
        "platform_xbox": "🚧 Xbox - In Testphase",
        "platform_x360": "🚧 Xbox 360 - In Testphase",
        "platform_roadmap": "📋 Plattformen in Entwicklung ansehen...",
        "platform_in_development": "Plattform in Entwicklung",
        "separator": "──────────────────────",
        "rom_file": "📂 ROM-Datei", "no_rom": "⚠️ Keine ROM ausgewählt", "select_rom": "📂 ROM auswählen",
        "extract_texts": "📄 Texte extrahieren", "optimize_data": "🧹 Daten optimieren",
        "extraction_progress": "Extraktionsfortschritt", "optimization_progress": "Optimierungsfortschritt",
        "waiting": "Warte auf Start...", "language_config": "🌍 Sprachkonfiguration",
        "source_language": "📖 Quellsprache (ROM)", "target_language": "🎯 Zielsprache",
        "translation_mode": "Übersetzungsmodus", "api_config": "API-Konfiguration",
        "api_key": "API-Schlüssel:", "workers": "Workers:", "timeout": "Timeout (s):",
        "use_cache": "Übersetzungs-Cache verwenden", "translation_progress": "Übersetzungsfortschritt",
        "translate_ai": "🤖 Mit KI übersetzen", "stop_translation": "🛑 Übersetzung stoppen",
        "original_rom": "📂 Original-ROM", "translated_file": "📄 Übersetzte Datei",
        "select_file": "📄 Datei auswählen", "output_rom": "💾 Übersetzte ROM (Ausgabe)",
        "reinsertion_progress": "Wiedereinfügungsfortschritt", "reinsert": "Übersetzung wiedereinfügen",
        "theme": "🎨 Visuelles Thema", "ui_language": "🌐 Sprache der Oberfläche", "font_family": "🔤 Schriftart der Oberfläche",
        "log": "Betriebsprotokoll", "restart": "Neu starten", "exit": "Beenden",
        "developer": "Entwickelt von: Celso (Solo-Entwickler)", "in_dev": "IN ENTWICKLUNG",
        "file_to_translate": "📄 Zu übersetzende Datei (Optimiert)", "no_file": "📄 Keine Datei ausgewählt",
        "help_support": "🆘 Hilfe und Support", "manual_guide": "📘 Professioneller Benutzerhandbuch:",
        "manual_guide_title": "📘 Professioneller Benutzerhandbuch",
        "manual_step_1": "Schritt 1: Extraktion", "manual_step_2": "Schritt 2: Optimierung",
        "manual_step_3": "Schritt 3: Übersetzung", "manual_step_4": "Schritt 4: Wiedereinfügung",
        "manual_step_1_title": "📖 Schritt 1: Textextraktion",
        "manual_step_2_title": "📖 Schritt 2: Datenoptimierung",
        "manual_step_3_title": "📖 Schritt 3: KI-Übersetzung",
        "manual_step_4_title": "📖 Schritt 4: ROM-Wiedereinfügung",
        "manual_step_1_content": "<h2>🎯 Ziel</h2><p>Alle übersetz

baren Texte aus ROM oder PC-Spiel extrahieren.</p>",
        "manual_step_2_content": "<h2>🎯 Ziel</h2><p>Duplikate und binären Müll entfernen, um bis zu 80% bei API-Aufrufen zu sparen.</p>",
        "manual_step_3_content": "<h2>🎯 Ziel</h2><p>Optimierte Texte mit KI übersetzen (Gemini oder Ollama).</p>",
        "manual_step_4_content": "<h2>🎯 Ziel</h2><p>Übersetzte Texte in Original-ROM wiedereinfügen.</p>",
        "btn_stop": "Übersetzung stoppen", "btn_close": "Schließen",
        "roadmap_item": "Kommende Konsolen (Roadmap)...", "roadmap_title": "Roadmap",
        "roadmap_desc": "Plattformen in Entwicklung:", "roadmap_header": "Plattformen in Entwicklung",
        "roadmap_description": "Diese Plattformen werden in zukünftigen Updates hinzugefügt:",
        "roadmap_note": "Hinweis: Updates sind kostenlos für Framework-Käufer.",
        "roadmap_cat_playstation": "PlayStation", "roadmap_cat_nintendo_classic": "Nintendo Classic",
        "roadmap_cat_nintendo_portable": "Nintendo Portable",
        "roadmap_cat_sega": "Sega", "roadmap_cat_xbox": "Xbox", "roadmap_cat_other": "Andere"
    },
    # Adicione os demais idiomas aqui (it, ja, ko, ru, zh, ar, hi, tr, pl, nl)
}

# Gerar arquivos JSON
for lang_code, data in translations_data.items():
    lang_name = data.pop("name")
    translation_file = I18N_DIR / f"{lang_code}.json"

    content = create_translation(lang_code, lang_name, data)

    with open(translation_file, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=4)

    print(f"✅ Criado: {translation_file.name}")

print(f"\n🎉 {len(translations_data)} arquivos de tradução gerados com sucesso!")
print(f"📂 Local: {I18N_DIR}")
