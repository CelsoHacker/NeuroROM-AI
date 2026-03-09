#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona explicação AUTO-DETECT em todas as 13 línguas restantes
"""

import json

# AUTO-DETECT explanations for all 13 remaining languages
AUTODETECT_SECTIONS = {
    "es": {
        "step": "PASO 2.5",
        "title": "Idioma de Origen (¡Ya Configurado!)",
        "field_name": "Idioma de Origen (ROM)",
        "text": "AUTO-DETECTAR",
        "already_set": "¡Ya está así!",
        "leave_it": "✅ ¡DÉJALO EN AUTO-DETECTAR! ¡No necesitas cambiarlo!",
        "what_is": "¿Qué es AUTO-DETECTAR?",
        "bullet1": "🔍 <b>El programa descubre solo</b> si el juego está en inglés, japonés, español, etc.",
        "bullet2": "✅ <b>No necesitas saber</b> cuál es el idioma del juego original",
        "bullet3": "✅ <b>Funciona con cualquier juego</b> - japonés, inglés, coreano, chino, etc.",
        "bullet4": "⚡ <b>Es automático</b> - ¡el programa detecta y traduce!",
        "tip": "💡 Solo cámbialo si estás absolutamente seguro del idioma original. ¡Pero dejarlo en AUTO-DETECTAR siempre es la mejor opción!"
    },
    "fr": {
        "step": "ÉTAPE 2.5",
        "title": "Langue Source (Déjà Configuré!)",
        "field_name": "Langue Source (ROM)",
        "text": "AUTO-DÉTECTER",
        "already_set": "Déjà défini!",
        "leave_it": "✅ LAISSEZ SUR AUTO-DÉTECTER! Pas besoin de changer!",
        "what_is": "Qu'est-ce que AUTO-DÉTECTER?",
        "bullet1": "🔍 <b>Le programme découvre tout seul</b> si le jeu est en anglais, japonais, espagnol, etc.",
        "bullet2": "✅ <b>Vous n'avez pas besoin de savoir</b> quelle est la langue du jeu original",
        "bullet3": "✅ <b>Fonctionne avec n'importe quel jeu</b> - japonais, anglais, coréen, chinois, etc.",
        "bullet4": "⚡ <b>C'est automatique</b> - le programme détecte et traduit!",
        "tip": "💡 Ne changez que si vous êtes absolument certain de la langue d'origine. Mais laisser sur AUTO-DÉTECTER est toujours la meilleure option!"
    },
    "de": {
        "step": "SCHRITT 2.5",
        "title": "Quellsprache (Bereits Konfiguriert!)",
        "field_name": "Quellsprache (ROM)",
        "text": "AUTO-ERKENNEN",
        "already_set": "Bereits eingestellt!",
        "leave_it": "✅ AUF AUTO-ERKENNEN LASSEN! Keine Änderung nötig!",
        "what_is": "Was ist AUTO-ERKENNEN?",
        "bullet1": "🔍 <b>Das Programm findet selbst heraus</b>, ob das Spiel auf Englisch, Japanisch, Spanisch usw. ist",
        "bullet2": "✅ <b>Sie müssen nicht wissen</b>, in welcher Sprache das Originalspiel ist",
        "bullet3": "✅ <b>Funktioniert mit jedem Spiel</b> - Japanisch, Englisch, Koreanisch, Chinesisch usw.",
        "bullet4": "⚡ <b>Es ist automatisch</b> - das Programm erkennt und übersetzt!",
        "tip": "💡 Nur ändern, wenn Sie absolut sicher über die Originalsprache sind. Aber AUTO-ERKENNEN ist immer die beste Option!"
    },
    "it": {
        "step": "PASSO 2.5",
        "title": "Lingua di Origine (Già Configurato!)",
        "field_name": "Lingua di Origine (ROM)",
        "text": "AUTO-RILEVA",
        "already_set": "Già impostato!",
        "leave_it": "✅ LASCIA SU AUTO-RILEVA! Non serve cambiare!",
        "what_is": "Cos'è AUTO-RILEVA?",
        "bullet1": "🔍 <b>Il programma scopre da solo</b> se il gioco è in inglese, giapponese, spagnolo, ecc.",
        "bullet2": "✅ <b>Non devi sapere</b> qual è la lingua del gioco originale",
        "bullet3": "✅ <b>Funziona con qualsiasi gioco</b> - giapponese, inglese, coreano, cinese, ecc.",
        "bullet4": "⚡ <b>È automatico</b> - il programma rileva e traduce!",
        "tip": "💡 Cambia solo se sei assolutamente certo della lingua originale. Ma lasciare su AUTO-RILEVA è sempre la migliore opzione!"
    },
    "ja": {
        "step": "ステップ2.5",
        "title": "元の言語（既に設定済み！）",
        "field_name": "元の言語（ROM）",
        "text": "自動検出",
        "already_set": "既に設定済み！",
        "leave_it": "✅ 自動検出のままにしてください！変更不要です！",
        "what_is": "自動検出とは？",
        "bullet1": "🔍 <b>プログラムが自動的に判別</b>ゲームが英語、日本語、スペイン語などかを",
        "bullet2": "✅ <b>元の言語を知る必要はありません</b>",
        "bullet3": "✅ <b>あらゆるゲームに対応</b> - 日本語、英語、韓国語、中国語など",
        "bullet4": "⚡ <b>自動です</b> - プログラムが検出して翻訳！",
        "tip": "💡 元の言語が確実にわかる場合のみ変更してください。自動検出のままが常に最良の選択です！"
    },
    "ko": {
        "step": "단계 2.5",
        "title": "원본 언어 (이미 설정됨!)",
        "field_name": "원본 언어 (ROM)",
        "text": "자동 감지",
        "already_set": "이미 설정됨!",
        "leave_it": "✅ 자동 감지로 두세요! 변경할 필요 없습니다!",
        "what_is": "자동 감지란?",
        "bullet1": "🔍 <b>프로그램이 스스로 판별</b>게임이 영어, 일본어, 스페인어 등인지",
        "bullet2": "✅ <b>원본 언어를 알 필요가 없습니다</b>",
        "bullet3": "✅ <b>모든 게임에서 작동</b> - 일본어, 영어, 한국어, 중국어 등",
        "bullet4": "⚡ <b>자동입니다</b> - 프로그램이 감지하고 번역!",
        "tip": "💡 원본 언어가 확실한 경우에만 변경하세요. 하지만 자동 감지로 두는 것이 항상 최선입니다!"
    },
    "zh": {
        "step": "步骤2.5",
        "title": "源语言（已配置！）",
        "field_name": "源语言（ROM）",
        "text": "自动检测",
        "already_set": "已设置！",
        "leave_it": "✅ 保持自动检测！无需更改！",
        "what_is": "什么是自动检测？",
        "bullet1": "🔍 <b>程序自动识别</b>游戏是英语、日语、西班牙语等",
        "bullet2": "✅ <b>您无需知道</b>原始游戏的语言",
        "bullet3": "✅ <b>适用于任何游戏</b> - 日语、英语、韩语、中文等",
        "bullet4": "⚡ <b>全自动</b> - 程序检测并翻译！",
        "tip": "💡 仅在您绝对确定原始语言时才更改。保持自动检测始终是最佳选择！"
    },
    "ru": {
        "step": "ШАГ 2.5",
        "title": "Исходный Язык (Уже Настроен!)",
        "field_name": "Исходный Язык (ROM)",
        "text": "АВТО-ОПРЕДЕЛЕНИЕ",
        "already_set": "Уже установлено!",
        "leave_it": "✅ ОСТАВЬТЕ АВТО-ОПРЕДЕЛЕНИЕ! Изменять не нужно!",
        "what_is": "Что такое АВТО-ОПРЕДЕЛЕНИЕ?",
        "bullet1": "🔍 <b>Программа сама определяет</b>, на английском, японском, испанском и т.д. игра",
        "bullet2": "✅ <b>Вам не нужно знать</b> язык оригинальной игры",
        "bullet3": "✅ <b>Работает с любой игрой</b> - японский, английский, корейский, китайский и т.д.",
        "bullet4": "⚡ <b>Автоматически</b> - программа определяет и переводит!",
        "tip": "💡 Меняйте только если абсолютно уверены в исходном языке. Но оставить АВТО-ОПРЕДЕЛЕНИЕ всегда лучший вариант!"
    },
    "ar": {
        "step": "الخطوة 2.5",
        "title": "اللغة المصدر (تم تكوينها بالفعل!)",
        "field_name": "اللغة المصدر (ROM)",
        "text": "كشف تلقائي",
        "already_set": "تم تعيينها بالفعل!",
        "leave_it": "✅ اتركها على الكشف التلقائي! لا حاجة للتغيير!",
        "what_is": "ما هو الكشف التلقائي؟",
        "bullet1": "🔍 <b>البرنامج يكتشف بنفسه</b> إذا كانت اللعبة بالإنجليزية أو اليابانية أو الإسبانية وما إلى ذلك",
        "bullet2": "✅ <b>لا تحتاج إلى معرفة</b> لغة اللعبة الأصلية",
        "bullet3": "✅ <b>يعمل مع أي لعبة</b> - يابانية، إنجليزية، كورية، صينية وما إلى ذلك",
        "bullet4": "⚡ <b>تلقائي</b> - البرنامج يكتشف ويترجم!",
        "tip": "💡 قم بالتغيير فقط إذا كنت متأكدًا تمامًا من اللغة الأصلية. لكن ترك الكشف التلقائي هو دائمًا الخيار الأفضل!"
    },
    "hi": {
        "step": "चरण 2.5",
        "title": "स्रोत भाषा (पहले से कॉन्फ़िगर!)",
        "field_name": "स्रोत भाषा (ROM)",
        "text": "ऑटो-डिटेक्ट",
        "already_set": "पहले से सेट!",
        "leave_it": "✅ ऑटो-डिटेक्ट पर छोड़ें! बदलने की जरूरत नहीं!",
        "what_is": "ऑटो-डिटेक्ट क्या है?",
        "bullet1": "🔍 <b>प्रोग्राम खुद पता लगाता है</b> कि गेम अंग्रेजी, जापानी, स्पेनिश आदि में है",
        "bullet2": "✅ <b>आपको जानने की जरूरत नहीं</b> मूल गेम की भाषा",
        "bullet3": "✅ <b>किसी भी गेम के साथ काम करता है</b> - जापानी, अंग्रेजी, कोरियाई, चीनी आदि",
        "bullet4": "⚡ <b>यह स्वचालित है</b> - प्रोग्राम पता लगाता है और अनुवाद करता है!",
        "tip": "💡 केवल तभी बदलें जब आप मूल भाषा के बारे में पूरी तरह सुनिश्चित हों। लेकिन ऑटो-डिटेक्ट पर छोड़ना हमेशा सबसे अच्छा विकल्प है!"
    },
    "tr": {
        "step": "ADIM 2.5",
        "title": "Kaynak Dil (Zaten Yapılandırılmış!)",
        "field_name": "Kaynak Dil (ROM)",
        "text": "OTOMATİK ALGILAMA",
        "already_set": "Zaten ayarlanmış!",
        "leave_it": "✅ OTOMATİK ALGILAMADA BIRAKIN! Değiştirmenize gerek yok!",
        "what_is": "OTOMATİK ALGILAMA nedir?",
        "bullet1": "🔍 <b>Program kendi başına bulur</b> oyunun İngilizce, Japonca, İspanyolca vb. olduğunu",
        "bullet2": "✅ <b>Bilmenize gerek yok</b> orijinal oyunun dilini",
        "bullet3": "✅ <b>Herhangi bir oyunla çalışır</b> - Japonca, İngilizce, Korece, Çince vb.",
        "bullet4": "⚡ <b>Otomatiktir</b> - program algılar ve çevirir!",
        "tip": "💡 Sadece orijinal dil konusunda kesinlikle eminseniz değiştirin. Ancak OTOMATİK ALGILAMA'da bırakmak her zaman en iyi seçenektir!"
    },
    "pl": {
        "step": "KROK 2.5",
        "title": "Język Źródłowy (Już Skonfigurowany!)",
        "field_name": "Język Źródłowy (ROM)",
        "text": "AUTO-WYKRYJ",
        "already_set": "Już ustawione!",
        "leave_it": "✅ ZOSTAW NA AUTO-WYKRYJ! Nie trzeba zmieniać!",
        "what_is": "Czym jest AUTO-WYKRYJ?",
        "bullet1": "🔍 <b>Program sam wykrywa</b>, czy gra jest po angielsku, japońsku, hiszpańsku itp.",
        "bullet2": "✅ <b>Nie musisz wiedzieć</b>, w jakim języku jest oryginalna gra",
        "bullet3": "✅ <b>Działa z każdą grą</b> - japońską, angielską, koreańską, chińską itp.",
        "bullet4": "⚡ <b>To automatyczne</b> - program wykrywa i tłumaczy!",
        "tip": "💡 Zmieniaj tylko jeśli jesteś absolutnie pewien oryginalnego języka. Ale zostawienie AUTO-WYKRYJ to zawsze najlepsza opcja!"
    },
    "nl": {
        "step": "STAP 2.5",
        "title": "Brontaal (Al Geconfigureerd!)",
        "field_name": "Brontaal (ROM)",
        "text": "AUTO-DETECTEER",
        "already_set": "Al ingesteld!",
        "leave_it": "✅ LAAT OP AUTO-DETECTEER! Hoeft niet gewijzigd!",
        "what_is": "Wat is AUTO-DETECTEER?",
        "bullet1": "🔍 <b>Het programma vindt zelf</b> of het spel in Engels, Japans, Spaans enz. is",
        "bullet2": "✅ <b>Je hoeft niet te weten</b> wat de taal van het originele spel is",
        "bullet3": "✅ <b>Werkt met elk spel</b> - Japans, Engels, Koreaans, Chinees enz.",
        "bullet4": "⚡ <b>Het is automatisch</b> - het programma detecteert en vertaalt!",
        "tip": "💡 Wijzig alleen als je absoluut zeker bent van de originele taal. Maar AUTO-DETECTEER laten staan is altijd de beste optie!"
    }
}

def build_step3_content_with_autodetect(lang_code, base_content):
    """Insert AUTO-DETECT section after STEP 2 in the manual"""
    section = AUTODETECT_SECTIONS[lang_code]

    # Build AUTO-DETECT section HTML
    autodetect_html = f"""<h3>🔹 {section['step']}: {section['title']}</h3><p>Logo abaixo você verá um campo chamado <b>"{section['field_name']}"</b> mostrando:</p><p style="background: #2d2d2d; padding: 10px; border-left: 4px solid #4CAF50;"><b>{section['text']}</b> ← <span style="color: #4CAF50;">✓ {section['already_set']}</span></p><p><b style="color: #4CAF50;">{section['leave_it']}</b></p><p><b>{section['what_is']}</b></p><ul><li>{section['bullet1']}</li><li>{section['bullet2']}</li><li>{section['bullet3']}</li><li>{section['bullet4']}</li></ul><p><i>{section['tip']}</i></p>"""

    # Find where to insert (after STEP 2 in the manual - looking for translation mode section)
    # We need to insert before the translation mode configuration step
    # Search for common patterns that indicate translation mode section

    if lang_code == "es":
        insert_marker = '<h3>🔹 PASO 3: Configurar el Modo de Traducción</h3>'
    elif lang_code == "fr":
        insert_marker = '<h3>🔹 ÉTAPE 3: Configurer le Mode de Traduction</h3>'
    elif lang_code == "de":
        insert_marker = '<h3>🔹 SCHRITT 3: Übersetzungsmodus Konfigurieren</h3>'
    elif lang_code == "it":
        insert_marker = '<h3>🔹 PASSO 3: Configurare la Modalità di Traduzione</h3>'
    elif lang_code == "ja":
        insert_marker = '<h3>🔹 ステップ3: 翻訳モードの設定</h3>'
    elif lang_code == "ko":
        insert_marker = '<h3>🔹 단계 3: 번역 모드 구성</h3>'
    elif lang_code == "zh":
        insert_marker = '<h3>🔹 步骤3: 配置翻译模式</h3>'
    elif lang_code == "ru":
        insert_marker = '<h3>🔹 ШАГ 3: Настройка Режима Перевода</h3>'
    elif lang_code == "ar":
        insert_marker = '<h3>🔹 الخطوة 3: تكوين وضع الترجمة</h3>'
    elif lang_code == "hi":
        insert_marker = '<h3>🔹 चरण 3: अनुवाद मोड कॉन्फ़िगर करें</h3>'
    elif lang_code == "tr":
        insert_marker = '<h3>🔹 ADIM 3: Çeviri Modunu Yapılandırma</h3>'
    elif lang_code == "pl":
        insert_marker = '<h3>🔹 KROK 3: Konfiguracja Trybu Tłumaczenia</h3>'
    elif lang_code == "nl":
        insert_marker = '<h3>🔹 STAP 3: Vertaalmodus Configureren</h3>'
    else:
        return base_content  # Skip if we don't have the marker

    # Insert AUTO-DETECT section before translation mode
    if insert_marker in base_content:
        return base_content.replace(insert_marker, autodetect_html + insert_marker)
    else:
        # Fallback: append at the end of Step 2 section
        return base_content + autodetect_html

def update_all_languages():
    """Update all 13 remaining languages with AUTO-DETECT explanation"""
    languages = ["es", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "hi", "tr", "pl", "nl"]

    for lang in languages:
        json_file = f"i18n/{lang}.json"

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Get current manual_step_3_content
            current_content = data.get('manual_step_3_content', '')

            # Check if AUTO-DETECT section already exists
            section = AUTODETECT_SECTIONS[lang]
            if section['step'] in current_content:
                print(f"⏭️  Skipping {lang}.json (AUTO-DETECT already present)")
                continue

            # Insert AUTO-DETECT explanation
            new_content = build_step3_content_with_autodetect(lang, current_content)
            data['manual_step_3_content'] = new_content

            # Save
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            print(f"✅ {lang}.json updated with AUTO-DETECT explanation!")

        except Exception as e:
            print(f"❌ Error updating {lang}.json: {e}")

# Run
print("=" * 70)
print("🔄 ADDING AUTO-DETECT TO ALL 13 REMAINING LANGUAGES")
print("=" * 70)
print()
update_all_languages()
print()
print("=" * 70)
print("✅ ALL LANGUAGES UPDATED WITH AUTO-DETECT EXPLANATION!")
print("=" * 70)
print()
