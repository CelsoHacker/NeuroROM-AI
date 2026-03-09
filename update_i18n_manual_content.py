#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to update all i18n files with simplified manual content.
This script applies the beginner-friendly manual content to all language files.
"""

import json
import os
from pathlib import Path

# Define the base directory
BASE_DIR = Path(__file__).parent
I18N_DIR = BASE_DIR / "i18n"

# Define the simplified content templates for each language
# This follows the same pattern as English and Spanish

LANGUAGE_UPDATES = {
    "de": {  # German
        "manual_step_1_content": '<h2>🎯 Was es tut</h2><p>Findet alle Texte in deiner ROM oder deinem PC-Spiel.</p><h2>📝 Wie man es benutzt</h2><ol><li>Wähle deine Plattform (SNES, PS1, GBA, PC)</li><li>Klicke auf "ROM auswählen"</li><li>Klicke auf "Texte extrahieren"</li><li>Warte, während das Programm arbeitet</li></ol><h2>✅ Was passieren wird</h2><ul><li>Eine Datei namens <code>spielname_extracted.txt</code> wird erstellt</li><li>Dauert 30 Sekunden bis 2 Minuten</li><li>Du siehst einen Fortschrittsbalken</li></ul>',

        "manual_step_2_content": '<h2>🎯 Was es tut</h2><p>Entfernt wiederholte Texte und Rauschen, damit die Übersetzung schneller und günstiger wird.</p><h2>📝 Wie man es benutzt</h2><ol><li>Klicke auf "Daten optimieren"</li><li>Warte ein paar Sekunden</li><li>Das war\'s! Das Programm reinigt automatisch</li></ol><h2>✅ Was passieren wird</h2><ul><li>Eine Datei <code>spielname_optimized.txt</code> wird erstellt</li><li>Die Datei wird viel kleiner sein (normalerweise 80% kleiner!)</li><li>Beispiel: 755.000 Zeilen → 150.000 Zeilen</li><li>Dauert 5-15 Sekunden</li></ul><h2>💡 Warum das nützlich ist</h2><ul><li>Übersetzt 5x schneller</li><li>Kostet weniger (weniger KI-Nutzung)</li><li>Entfernt nutzlose Texte wie "XXXX" oder "????"</li></ul>',

        "manual_step_3_content": '<h2>🎯 Was es tut</h2><p>Verwendet einen Übersetzer-Roboter (KI), um deine Texte automatisch zu übersetzen.</p><h2>🚀 AUTO MODUS (Empfohlen - Einfach!)</h2><p>Das ist am einfachsten! Das Programm verwendet:</p><ul><li><b>Erst Gemini</b> (schnell, 20x kostenlos/Tag)</li><li><b>Dann Ollama</b> (auf deinem PC, unbegrenzt aber langsamer)</li><li>Hol dir deinen kostenlosen Schlüssel: <b>https://aistudio.google.com/apikey</b></li><li>Lade Ollama herunter: <b>https://ollama.com</b></li></ul><h2>📝 Wie man es benutzt</h2><ol><li>Wähle die Datei <code>*_optimized.txt</code></li><li>AUTO Modus: Füge deinen Gemini-Schlüssel ein (oder lass es leer für nur Ollama)</li><li>Klicke auf "Mit KI übersetzen"</li><li>Warte (15-45 Minuten für große Spiele)</li></ol><h2>✅ Was passieren wird</h2><ul><li>Eine Datei <code>spielname_translated.txt</code> wird erstellt</li><li>Das Programm übersetzt alles automatisch</li><li>Du kannst schließen und später weitermachen!</li></ul><h2>💻 Was du brauchst (Computer)</h2><p><b>Basis-PC:</b> Jeder PC mit 8GB RAM (langsam aber funktioniert)</p><p><b>Guter PC:</b> 16GB RAM + Nvidia Grafikkarte (RTX 3060 oder besser) = schnell!</p><p><b>Leistungsstarker PC:</b> 32GB RAM + RTX 4090 = super schnell!</p>',

        "manual_step_4_content": '<h2>🎯 Was es tut</h2><p>Fügt die übersetzten Texte zurück in dein Spiel ein, um die finale Version zu erstellen.</p><h2>📝 Wie man es benutzt</h2><ol><li>Wähle die Original-ROM (.smc, .bin, usw.)</li><li>Wähle die Datei <code>*_translated.txt</code></li><li>Gib deiner übersetzten ROM einen Namen</li><li>Klicke auf "Wiedereinfügen"</li></ol><h2>✅ Was passieren wird</h2><ul><li>Deine übersetzte ROM wird erstellt!</li><li>Dauert 10-60 Sekunden</li><li>Dein Originalspiel wird automatisch gesichert</li></ul><h2>🧪 Teste dein übersetztes Spiel</h2><p><b>Was ist ein Emulator?</b> Ein Programm, das alte Spiele auf deinem PC laufen lässt!</p><ul><li><b>Für SNES:</b> Lade SNES9x herunter</li><li><b>Für PlayStation:</b> Lade ePSXe herunter</li><li><b>Für GBA:</b> Lade VisualBoy Advance herunter</li></ul><p><b>Wie testen:</b></p><ol><li>Öffne deine übersetzte ROM im Emulator</li><li>Schau dir die Menüs an</li><li>Rede mit Charakteren</li><li>Überprüfe, ob alles richtig angezeigt wird</li></ol><h2>🔧 Wenn etwas nicht stimmt</h2><ul><li><b>Abgeschnittener Text:</b> Die Übersetzung ist zu lang, versuche kürzere Wörter</li><li><b>Seltsame Symbole:</b> Kontaktiere den Support</li><li><b>Das Spiel startet nicht:</b> Stelle sicher, dass du die richtige ROM verwendest</li></ul>',

        "help_step3_objective_title": "Was es tut",
        "help_step3_objective_text": "Verwendet einen Übersetzer-Roboter für automatische Übersetzung.",
        "help_step3_instructions_title": "Wie man es benutzt",
        "help_step3_instructions_text": "1. Wähle die Datei *_optimized.txt\n2. AUTO Modus empfohlen\n3. Füge deinen kostenlosen Gemini-Schlüssel ein\n4. Klicke auf 'Mit KI übersetzen'",
        "help_step3_expect_title": "Was passieren wird",
        "help_step3_expect_text": "Erstellte Datei: *_translated.txt\nZeit: 15-45 Minuten\nDu kannst schließen und weitermachen!",
        "help_step3_automode_title": "AUTO Modus (Empfohlen)",
        "help_step3_automode_text": "Verwendet Gemini (schnell, 20x kostenlos/Tag) dann Ollama (unbegrenzt). Die beste Wahl!"
    },

    "it": {  # Italian
        "manual_step_1_content": '<h2>🎯 Cosa fa</h2><p>Trova tutti i testi nella tua ROM o gioco PC.</p><h2>📝 Come usarlo</h2><ol><li>Scegli la tua piattaforma (SNES, PS1, GBA, PC)</li><li>Clicca su "Seleziona ROM"</li><li>Clicca su "Estrai Testi"</li><li>Aspetta mentre il programma lavora</li></ol><h2>✅ Cosa succederà</h2><ul><li>Verrà creato un file chiamato <code>nome_gioco_extracted.txt</code></li><li>Ci vogliono 30 secondi a 2 minuti</li><li>Vedrai una barra di avanzamento</li></ul>',

        "manual_step_2_content": '<h2>🎯 Cosa fa</h2><p>Rimuove testi ripetuti e rumore per rendere la traduzione più veloce ed economica.</p><h2>📝 Come usarlo</h2><ol><li>Clicca su "Ottimizza Dati"</li><li>Aspetta qualche secondo</li><li>Fatto! Il programma pulisce automaticamente</li></ol><h2>✅ Cosa succederà</h2><ul><li>Verrà creato un file <code>nome_gioco_optimized.txt</code></li><li>Il file sarà molto più piccolo (generalmente 80% più piccolo!)</li><li>Esempio: 755.000 righe → 150.000 righe</li><li>Ci vogliono 5-15 secondi</li></ul><h2>💡 Perché è utile</h2><ul><li>Traduce 5 volte più velocemente</li><li>Costa meno (meno uso di IA)</li><li>Rimuove testi inutili come "XXXX" o "????"</li></ul>',

        "manual_step_3_content": '<h2>🎯 Cosa fa</h2><p>Usa un robot traduttore (IA) per tradurre automaticamente i tuoi testi.</p><h2>🚀 MODALITÀ AUTO (Consigliata - Facile!)</h2><p>È la più semplice! Il programma usa:</p><ul><li><b>Prima Gemini</b> (veloce, 20x gratis/giorno)</li><li><b>Poi Ollama</b> (sul tuo PC, illimitato ma più lento)</li><li>Ottieni la tua chiave gratis: <b>https://aistudio.google.com/apikey</b></li><li>Scarica Ollama: <b>https://ollama.com</b></li></ul><h2>📝 Come usarlo</h2><ol><li>Scegli il file <code>*_optimized.txt</code></li><li>Modalità AUTO: Incolla la tua chiave Gemini (o lascia vuoto per solo Ollama)</li><li>Clicca su "Traduci con IA"</li><li>Aspetta (15-45 minuti per giochi grandi)</li></ol><h2>✅ Cosa succederà</h2><ul><li>Verrà creato un file <code>nome_gioco_translated.txt</code></li><li>Il programma traduce tutto automaticamente</li><li>Puoi chiudere e riprendere dopo!</li></ul><h2>💻 Di cosa hai bisogno (Computer)</h2><p><b>PC Base:</b> Qualsiasi PC con 8GB di RAM (lento ma funziona)</p><p><b>PC Buono:</b> 16GB RAM + scheda grafica Nvidia (RTX 3060 o meglio) = veloce!</p><p><b>PC Potente:</b> 32GB RAM + RTX 4090 = super veloce!</p>',

        "manual_step_4_content": '<h2>🎯 Cosa fa</h2><p>Rimette i testi tradotti nel tuo gioco per creare la versione finale.</p><h2>📝 Come usarlo</h2><ol><li>Scegli la ROM originale (.smc, .bin, ecc.)</li><li>Scegli il file <code>*_translated.txt</code></li><li>Dai un nome alla tua ROM tradotta</li><li>Clicca su "Reinserisci"</li></ol><h2>✅ Cosa succederà</h2><ul><li>La tua ROM tradotta sarà creata!</li><li>Ci vogliono 10-60 secondi</li><li>Il tuo gioco originale è salvato automaticamente</li></ul><h2>🧪 Testa il tuo gioco tradotto</h2><p><b>Cos\'è un emulatore?</b> Un programma che fa girare i vecchi giochi sul tuo PC!</p><ul><li><b>Per SNES:</b> Scarica SNES9x</li><li><b>Per PlayStation:</b> Scarica ePSXe</li><li><b>Per GBA:</b> Scarica VisualBoy Advance</li></ul><p><b>Come testare:</b></p><ol><li>Apri la tua ROM tradotta nell\'emulatore</li><li>Guarda i menu</li><li>Parla con i personaggi</li><li>Verifica che tutto si visualizzi bene</li></ol><h2>🔧 Se qualcosa non va</h2><ul><li><b>Testo tagliato:</b> La traduzione è troppo lunga, prova parole più corte</li><li><b>Simboli strani:</b> Contatta il supporto</li><li><b>Il gioco non si avvia:</b> Assicurati di usare la ROM giusta</li></ul>',

        "help_step3_objective_title": "Cosa fa",
        "help_step3_objective_text": "Usa un robot traduttore per tradurre automaticamente.",
        "help_step3_instructions_title": "Come usarlo",
        "help_step3_instructions_text": "1. Scegli il file *_optimized.txt\n2. Modalità AUTO consigliata\n3. Incolla la tua chiave Gemini gratis\n4. Clicca su 'Traduci con IA'",
        "help_step3_expect_title": "Cosa succederà",
        "help_step3_expect_text": "File creato: *_translated.txt\nTempo: 15-45 minuti\nPuoi chiudere e riprendere!",
        "help_step3_automode_title": "Modalità AUTO (Consigliata)",
        "help_step3_automode_text": "Usa Gemini (veloce, 20x gratis/giorno) poi Ollama (illimitato). La scelta migliore!"
    },

    # Continuing with remaining languages...
    # Note: This is a template - the full script would contain all 11 languages
}

def update_i18n_file(language_code, updates):
    """Update a single i18n file with simplified manual content."""
    file_path = I18N_DIR / f"{language_code}.json"

    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        return False

    try:
        # Read the existing file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Update the fields
        for key, value in updates.items():
            if key in data:
                data[key] = value
                print(f"  ✓ Updated {key}")
            else:
                print(f"  ⚠️  Key not found: {key}")

        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"✅ Successfully updated {language_code}.json")
        return True

    except Exception as e:
        print(f"❌ Error updating {language_code}.json: {e}")
        return False

def main():
    """Main function to update all i18n files."""
    print("=" * 60)
    print("ROM Translation Framework - i18n Manual Content Update")
    print("=" * 60)
    print()

    success_count = 0
    total_count = len(LANGUAGE_UPDATES)

    for lang_code, updates in LANGUAGE_UPDATES.items():
        print(f"\nUpdating {lang_code}.json...")
        if update_i18n_file(lang_code, updates):
            success_count += 1

    print()
    print("=" * 60)
    print(f"Update Complete: {success_count}/{total_count} files updated successfully")
    print("=" * 60)

if __name__ == "__main__":
    main()
