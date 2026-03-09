#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TASK 1: Remove ALL roadmap references from all 15 i18n JSON files
TASK 2: Add congratulations_title and congratulations_message to all 13 remaining languages
"""

import json
import os

# Congratulations messages for all languages
CONGRATULATIONS = {
    "es": {
        "congratulations_title": "🎉 ¡Felicidades!",
        "congratulations_message": "🎊 ¡Tradujiste tu primer juego!\n\n✅ ¡Traducción completa!\n✅ ¡Juego creado con éxito!\n✅ ¡Todo funcionando perfectamente!\n\n¡Ahora solo juega y diviértete! 🎮✨"
    },
    "fr": {
        "congratulations_title": "🎉 Félicitations!",
        "congratulations_message": "🎊 Vous avez traduit votre premier jeu!\n\n✅ Traduction terminée!\n✅ Jeu créé avec succès!\n✅ Tout fonctionne parfaitement!\n\nMaintenant, il ne reste plus qu'à jouer et s'amuser! 🎮✨"
    },
    "de": {
        "congratulations_title": "🎉 Glückwunsch!",
        "congratulations_message": "🎊 Sie haben Ihr erstes Spiel übersetzt!\n\n✅ Übersetzung abgeschlossen!\n✅ Spiel erfolgreich erstellt!\n✅ Alles funktioniert perfekt!\n\nJetzt einfach spielen und Spaß haben! 🎮✨"
    },
    "it": {
        "congratulations_title": "🎉 Congratulazioni!",
        "congratulations_message": "🎊 Hai tradotto il tuo primo gioco!\n\n✅ Traduzione completata!\n✅ Gioco creato con successo!\n✅ Tutto funziona perfettamente!\n\nOra gioca e divertiti! 🎮✨"
    },
    "ja": {
        "congratulations_title": "🎉 おめでとうございます!",
        "congratulations_message": "🎊 最初のゲームを翻訳しました!\n\n✅ 翻訳完了!\n✅ ゲーム作成成功!\n✅ すべて完璧に動作しています!\n\nさあ、プレイして楽しみましょう! 🎮✨"
    },
    "ko": {
        "congratulations_title": "🎉 축하합니다!",
        "congratulations_message": "🎊 첫 게임을 번역했습니다!\n\n✅ 번역 완료!\n✅ 게임 생성 성공!\n✅ 모든 것이 완벽하게 작동합니다!\n\n이제 플레이하고 즐기세요! 🎮✨"
    },
    "zh": {
        "congratulations_title": "🎉 恭喜！",
        "congratulations_message": "🎊 您翻译了您的第一个游戏！\n\n✅ 翻译完成！\n✅ 游戏创建成功！\n✅ 一切运行完美！\n\n现在去玩吧，尽情享受！ 🎮✨"
    },
    "ru": {
        "congratulations_title": "🎉 Поздравляем!",
        "congratulations_message": "🎊 Вы перевели свою первую игру!\n\n✅ Перевод завершен!\n✅ Игра успешно создана!\n✅ Все работает отлично!\n\nТеперь просто играйте и наслаждайтесь! 🎮✨"
    },
    "ar": {
        "congratulations_title": "🎉 تهانينا!",
        "congratulations_message": "🎊 لقد ترجمت لعبتك الأولى!\n\n✅ اكتملت الترجمة!\n✅ تم إنشاء اللعبة بنجاح!\n✅ كل شيء يعمل بشكل مثالي!\n\nالآن فقط العب واستمتع! 🎮✨"
    },
    "hi": {
        "congratulations_title": "🎉 बधाई हो!",
        "congratulations_message": "🎊 आपने अपना पहला गेम अनुवादित किया!\n\n✅ अनुवाद पूर्ण!\n✅ गेम सफलतापूर्वक बनाया गया!\n✅ सब कुछ पूरी तरह से काम कर रहा है!\n\nअब बस खेलें और मज़े करें! 🎮✨"
    },
    "tr": {
        "congratulations_title": "🎉 Tebrikler!",
        "congratulations_message": "🎊 İlk oyununuzu çevirdiniz!\n\n✅ Çeviri tamamlandı!\n✅ Oyun başarıyla oluşturuldu!\n✅ Her şey mükemmel çalışıyor!\n\nŞimdi sadece oynayın ve eğlenin! 🎮✨"
    },
    "pl": {
        "congratulations_title": "🎉 Gratulacje!",
        "congratulations_message": "🎊 Przetłumaczyłeś swoją pierwszą grę!\n\n✅ Tłumaczenie zakończone!\n✅ Gra utworzona pomyślnie!\n✅ Wszystko działa idealnie!\n\nTeraz po prostu graj i baw się! 🎮✨"
    },
    "nl": {
        "congratulations_title": "🎉 Gefeliciteerd!",
        "congratulations_message": "🎊 Je hebt je eerste spel vertaald!\n\n✅ Vertaling voltooid!\n✅ Spel succesvol aangemaakt!\n✅ Alles werkt perfect!\n\nNu gewoon spelen en plezier hebben! 🎮✨"
    }
}

def process_language(lang_code, lang_data):
    """Process a single language: remove roadmap keys, add congratulations"""

    # Keys to remove (all roadmap-related)
    roadmap_keys = [
        "roadmap_item", "roadmap_title", "roadmap_desc",
        "roadmap_header", "roadmap_description", "roadmap_note",
        "roadmap_cat_playstation", "roadmap_cat_nintendo_classic",
        "roadmap_cat_nintendo_portable", "roadmap_cat_sega",
        "roadmap_cat_xbox", "roadmap_cat_other"
    ]

    # Remove roadmap keys
    for key in roadmap_keys:
        if key in lang_data:
            del lang_data[key]
            print(f"   🗑️  Removed: {key}")

    # Add congratulations if not already present
    if lang_code in CONGRATULATIONS:
        if "congratulations_title" not in lang_data:
            lang_data["congratulations_title"] = CONGRATULATIONS[lang_code]["congratulations_title"]
            print(f"   ✅ Added: congratulations_title")
        if "congratulations_message" not in lang_data:
            lang_data["congratulations_message"] = CONGRATULATIONS[lang_code]["congratulations_message"]
            print(f"   ✅ Added: congratulations_message")

    return lang_data

def update_all_languages():
    """Update all 15 i18n JSON files"""

    i18n_dir = "i18n"
    languages = ["pt", "en", "es", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "hi", "tr", "pl", "nl"]

    for lang in languages:
        json_file = os.path.join(i18n_dir, f"{lang}.json")

        if not os.path.exists(json_file):
            print(f"⚠️  Skipping {lang}.json (not found)")
            continue

        print(f"\n🔄 Processing {lang}.json...")

        # Read
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Process
        data = process_language(lang, data)

        # Write
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"✅ {lang}.json updated!")

# Run
print("=" * 70)
print("🚀 REMOVING ROADMAP + ADDING CONGRATULATIONS TO ALL 15 LANGUAGES")
print("=" * 70)

update_all_languages()

print("\n" + "=" * 70)
print("✅ ALL 15 LANGUAGES UPDATED SUCCESSFULLY!")
print("=" * 70)
print("\n📋 Changes made:")
print("   🗑️  Removed ALL roadmap-related keys from all files")
print("   ✅ Added congratulations_title & congratulations_message to:")
print("      es, fr, de, it, ja, ko, zh, ru, ar, hi, tr, pl, nl")
print("   ✅ pt and en already had these strings")
print()
