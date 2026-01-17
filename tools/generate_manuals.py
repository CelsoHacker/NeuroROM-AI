#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeuroROM AI - Professional Manual Generator (PDF)
==================================================

Generates multi-language PDF manuals with REAL Unicode font embedding using ReportLab.

Author: Celso (Programador Solo)
Email: celsoexpert@gmail.com
GitHub: https://github.com/CelsoHacker/NeuroROM-AI
Version: v5.3 Stable
© 2025 All Rights Reserved
"""

import sys
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def load_translations():
    """Load TRANSLATIONS dictionary from interface_tradutor_final.py"""
    interface_path = os.path.join(os.path.dirname(__file__), '..', 'interface')
    sys.path.insert(0, interface_path)

    try:
        import interface_tradutor_final
        import importlib
        importlib.reload(interface_tradutor_final)
        from interface_tradutor_final import ProjectConfig
        return ProjectConfig.TRANSLATIONS
    except Exception as e:
        print(f"⚠️  Could not load translations from interface: {e}")
        return {}


class ManualGenerator:
    """Generates professional PDF manuals with REAL Unicode fonts."""

    LANGUAGE_NAMES = {
        "pt": "Português (Brasil)",
        "en": "English",
        "es": "Español",
        "fr": "Français",
        "de": "Deutsch",
        "it": "Italiano",
        "ja": "日本語",
        "ko": "한국어",
        "zh": "中文",
        "ru": "Русский"
    }

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.translations = load_translations()
        self._register_fonts()

    def _register_fonts(self):
        """Register TTF fonts for all languages - these WILL be embedded."""
        fonts_dir = Path(__file__).parent.parent / "fonts"

        try:
            # Register CJK fonts
            pdfmetrics.registerFont(TTFont('NotoSansCJKjp', str(fonts_dir / 'NotoSansCJKjp-Regular.ttf')))
            pdfmetrics.registerFont(TTFont('NotoSansCJKkr', str(fonts_dir / 'NotoSansCJKkr-Regular.ttf')))
            pdfmetrics.registerFont(TTFont('NotoSansCJKsc', str(fonts_dir / 'NotoSansCJKsc-Regular.ttf')))

            # Register Latin/Cyrillic font
            pdfmetrics.registerFont(TTFont('NotoSans', str(fonts_dir / 'NotoSans-Regular.ttf')))

            print("✓ Registered TTF fonts (WILL BE EMBEDDED)")
            print("  - Japanese: NotoSansCJKjp-Regular.ttf")
            print("  - Korean: NotoSansCJKkr-Regular.ttf")
            print("  - Chinese: NotoSansCJKsc-Regular.ttf")
            print("  - Latin/Cyrillic: NotoSans-Regular.ttf")
        except Exception as e:
            print(f"⚠️  TTF font registration failed: {e}")
            print(f"   Fonts directory: {fonts_dir}")
            raise

    def _get_font_for_language(self, lang_code: str) -> str:
        """Get appropriate embedded TTF font for language."""
        if lang_code == 'ja':
            return 'NotoSansCJKjp'
        elif lang_code == 'zh':
            return 'NotoSansCJKsc'
        elif lang_code == 'ko':
            return 'NotoSansCJKkr'
        else:
            # For RU, PT, EN, ES, FR, DE, IT
            return 'NotoSans'

    def _create_styles(self, lang_code: str):
        """Create paragraph styles with TTF fonts."""
        font_name = self._get_font_for_language(lang_code)

        styles = {
            'title': ParagraphStyle(
                'CustomTitle',
                fontName=font_name,
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                alignment=TA_CENTER,
                spaceAfter=12,
                leading=28
            ),
            'subtitle': ParagraphStyle(
                'CustomSubtitle',
                fontName=font_name,
                fontSize=14,
                textColor=colors.HexColor('#4a4a4a'),
                alignment=TA_CENTER,
                spaceAfter=20,
                leading=18
            ),
            'heading1': ParagraphStyle(
                'CustomHeading1',
                fontName=font_name,
                fontSize=16,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=12,
                spaceBefore=12,
                leading=20
            ),
            'body': ParagraphStyle(
                'CustomBody',
                fontName=font_name,
                fontSize=10,
                textColor=colors.HexColor('#2c3e50'),
                alignment=TA_JUSTIFY,
                spaceAfter=10,
                leading=13
            ),
        }
        return styles

    def _get_translated_text(self, lang_code: str, key: str, default: str = "") -> str:
        """Get translated text from TRANSLATIONS dictionary."""
        if lang_code in self.translations:
            return self.translations[lang_code].get(key, default)
        return default

    def generate_manual(self, language: str = "pt") -> Path:
        """Generate PDF manual with EMBEDDED fonts."""
        print(f"📄 Generating {self.LANGUAGE_NAMES.get(language, language)} manual...")

        output_file = self.output_dir / f"NeuroROM_AI_v5.3_Manual_{language.upper()}.pdf"

        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        styles = self._create_styles(language)
        story = []

        # TITLE
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("NeuroROM AI v5.3", styles['title']))
        story.append(Paragraph(
            self._get_translated_text(language, 'title', 'Universal Localization Suite'),
            styles['subtitle']
        ))
        story.append(Spacer(1, 0.5*inch))

        # DEVELOPER INFO
        story.append(Paragraph(
            f"<b>{self._get_translated_text(language, 'developer', 'Developed by: Celso')}</b>",
            styles['body']
        ))
        story.append(Paragraph("<b>Email:</b> celsoexpert@gmail.com", styles['body']))
        story.append(Paragraph("<b>GitHub:</b> https://github.com/CelsoHacker/NeuroROM-AI", styles['body']))
        story.append(Paragraph("<b>© 2025 All Rights Reserved</b>", styles['body']))
        story.append(Spacer(1, 0.5*inch))

        # FEATURES
        story.append(Paragraph("MAIN FEATURES", styles['heading1']))

        features = {
            'pt': ["Extração automática", "Tradução com IA", "Suporte multi-plataforma"],
            'en': ["Automatic extraction", "AI translation", "Multi-platform support"],
            'ja': ["自動抽出", "AI翻訳", "マルチプラットフォーム対応"],
            'ko': ["자동 추출", "AI 번역", "멀티 플랫폼 지원"],
            'zh': ["自动提取", "AI翻译", "多平台支持"],
            'ru': ["Автоматическое извлечение", "ИИ перевод", "Поддержка нескольких платформ"]
        }

        for feature in features.get(language, features['en']):
            story.append(Paragraph(f"✓ {feature}", styles['body']))

        story.append(Spacer(1, 0.3*inch))

        # WORKFLOW
        story.append(Paragraph("WORKFLOW", styles['heading1']))

        workflow = {
            'pt': ["1. Extração - Selecione a ROM", "2. Tradução - Configure idiomas", "3. Reinserção - Gere ROM traduzida"],
            'en': ["1. Extraction - Select ROM", "2. Translation - Configure languages", "3. Reinsertion - Generate translated ROM"],
            'ja': ["1. 抽出 - ROMを選択", "2. 翻訳 - 言語を設定", "3. 再挿入 - 翻訳済みROMを生成"],
            'ko': ["1. 추출 - ROM 선택", "2. 번역 - 언어 설정", "3. 재삽입 - 번역된 ROM 생성"],
            'zh': ["1. 提取 - 选择ROM", "2. 翻译 - 配置语言", "3. 重新插入 - 生成翻译的ROM"],
            'ru': ["1. Извлечение - Выберите ROM", "2. Перевод - Настройте языки", "3. Реинсерция - Создайте переведенный ROM"]
        }

        for step in workflow.get(language, workflow['en']):
            story.append(Paragraph(step, styles['body']))

        story.append(Spacer(1, 0.3*inch))

        # ADD MORE CONTENT TO FORCE FONT EMBEDDING
        story.append(Paragraph("SUPPORTED PLATFORMS", styles['heading1']))

        platforms = {
            'pt': [
                "Nintendo Entertainment System (NES/Famicom) - Jogos clássicos de 8 bits",
                "Super Nintendo (SNES/Super Famicom) - Biblioteca de 16 bits com milhares de títulos",
                "Game Boy / Game Boy Color - Portáteis clássicos da Nintendo",
                "Game Boy Advance - Handheld de 32 bits com gráficos avançados",
                "Nintendo DS - Sistema de tela dupla com touchscreen",
                "Sega Genesis / Mega Drive - Console de 16 bits da Sega",
                "PlayStation 1 - Primeira geração PlayStation com CD-ROM",
                "Nintendo 64 - Console 3D da Nintendo com cartuchos",
                "Dreamcast - Último console da Sega com suporte online",
                "Atari 2600 - Pioneer dos videogames domésticos"
            ],
            'en': [
                "Nintendo Entertainment System (NES/Famicom) - Classic 8-bit gaming",
                "Super Nintendo (SNES/Super Famicom) - 16-bit library with thousands of titles",
                "Game Boy / Game Boy Color - Classic Nintendo handhelds",
                "Game Boy Advance - 32-bit handheld with advanced graphics",
                "Nintendo DS - Dual-screen system with touchscreen",
                "Sega Genesis / Mega Drive - Sega's 16-bit powerhouse",
                "PlayStation 1 - First generation PlayStation with CD-ROM",
                "Nintendo 64 - Nintendo's 3D console with cartridges",
                "Dreamcast - Sega's last console with online support",
                "Atari 2600 - Pioneer of home video gaming"
            ],
            'ja': [
                "ファミリーコンピュータ（ファミコン）- 8ビットの名作ゲーム機",
                "スーパーファミコン - 数千のタイトルを持つ16ビットライブラリ",
                "ゲームボーイ / ゲームボーイカラー - 任天堂の携帯ゲーム機",
                "ゲームボーイアドバンス - 32ビットハンドヘルド、高度なグラフィックス",
                "ニンテンドーDS - タッチスクリーン搭載のデュアルスクリーンシステム",
                "メガドライブ - セガの16ビットパワーハウス",
                "プレイステーション1 - CD-ROM搭載の第一世代プレイステーション",
                "ニンテンドー64 - カートリッジ採用の3Dコンソール",
                "ドリームキャスト - オンライン対応のセガ最後のコンソール",
                "アタリ2600 - 家庭用ビデオゲームの先駆者"
            ],
            'ko': [
                "패미컴 / NES - 8비트 클래식 게임기",
                "슈퍼 패미컴 / SNES - 수천 개의 타이틀을 보유한 16비트 라이브러리",
                "게임보이 / 게임보이 컬러 - 닌텐도의 클래식 휴대용 게임기",
                "게임보이 어드밴스 - 고급 그래픽을 갖춘 32비트 휴대용",
                "닌텐도 DS - 터치스크린이 있는 듀얼 스크린 시스템",
                "세가 메가 드라이브 / 제네시스 - 세가의 16비트 강자",
                "플레이스테이션 1 - CD-ROM이 있는 1세대 플레이스테이션",
                "닌텐도 64 - 카트리지를 사용하는 닌텐도의 3D 콘솔",
                "드림캐스트 - 온라인 지원을 갖춘 세가의 마지막 콘솔",
                "아타리 2600 - 가정용 비디오 게임의 선구자"
            ],
            'zh': [
                "红白机 / NES - 经典8位游戏机",
                "超级任天堂 / SNES - 拥有数千款游戏的16位库",
                "Game Boy / Game Boy Color - 任天堂经典掌机",
                "Game Boy Advance - 具有高级图形的32位掌机",
                "任天堂DS - 带触摸屏的双屏系统",
                "世嘉五代 / Mega Drive - 世嘉的16位强机",
                "PlayStation 1 - 带CD-ROM的第一代PlayStation",
                "任天堂64 - 使用卡带的任天堂3D主机",
                "Dreamcast - 具有在线支持的世嘉最后一台主机",
                "雅达利2600 - 家用电子游戏的先驱"
            ],
            'ru': [
                "Nintendo Entertainment System (NES/Famicom) - Классическая 8-битная игровая система",
                "Super Nintendo (SNES/Super Famicom) - 16-битная библиотека с тысячами игр",
                "Game Boy / Game Boy Color - Классические портативные консоли Nintendo",
                "Game Boy Advance - 32-битная портативная консоль с продвинутой графикой",
                "Nintendo DS - Система с двумя экранами и сенсорным экраном",
                "Sega Genesis / Mega Drive - 16-битная мощная консоль Sega",
                "PlayStation 1 - Первое поколение PlayStation с CD-ROM",
                "Nintendo 64 - 3D-консоль Nintendo с картриджами",
                "Dreamcast - Последняя консоль Sega с онлайн-поддержкой",
                "Atari 2600 - Пионер домашних видеоигр"
            ]
        }

        for platform in platforms.get(language, platforms['en']):
            story.append(Paragraph(f"• {platform}", styles['body']))

        # Build PDF
        doc.build(story)

        # CHECK FILE SIZE AND VERIFY EMBEDDING
        size_kb = output_file.stat().st_size / 1024
        print(f"✅ Generated: {output_file.name} ({size_kb:.1f} KB)")

        # Verify font embedding by checking for FontFile2 in PDF
        with open(output_file, 'rb') as f:
            pdf_content = f.read()
            is_embedded = b'/FontFile2' in pdf_content

        if is_embedded:
            print(f"   ✓ Font embedded (subset) - rendering will work offline")
        else:
            print(f"   ⚠️  WARNING: Font may not be embedded!")

        return output_file

    def generate_all_manuals(self):
        """Generate PDF manuals for all supported languages."""
        print("=" * 70)
        print("📚 NeuroROM AI v5.3 - Professional PDF Manual Generator (ReportLab)")
        print("=" * 70)
        print()

        generated = []

        for lang_code in self.LANGUAGE_NAMES.keys():
            try:
                manual_path = self.generate_manual(lang_code)
                generated.append(manual_path)
            except Exception as e:
                print(f"❌ Error generating {lang_code} manual: {e}")
                import traceback
                traceback.print_exc()

        print()
        print("=" * 70)
        print(f"✅ Successfully generated {len(generated)}/{len(self.LANGUAGE_NAMES)} PDF manuals")
        print("=" * 70)
        print()

        if generated:
            print("Generated PDF files:")
            for manual in generated:
                size_kb = manual.stat().st_size / 1024

                # Verify embedding by checking for FontFile2
                with open(manual, 'rb') as f:
                    is_embedded = b'/FontFile2' in f.read()

                status = "✓" if is_embedded else "⚠️"
                embed_status = "embedded" if is_embedded else "NOT embedded"

                print(f"  {status} {manual.name} ({size_kb:.1f} KB) - Font {embed_status}")
            print()

        return generated


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    manuals_dir = project_root / "docs" / "manuals"

    print(f"Project root: {project_root}")
    print(f"Output directory: {manuals_dir}")
    print()

    generator = ManualGenerator(manuals_dir)
    generated = generator.generate_all_manuals()

    if generated:
        print("🎉 PDF manual generation complete!")
    else:
        print("❌ No manuals were generated")
        sys.exit(1)


if __name__ == '__main__':
    main()
