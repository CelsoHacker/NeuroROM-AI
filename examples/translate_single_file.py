# -*- coding: utf-8 -*-
"""
================================================================================
SINGLE FILE TRANSLATOR - Translate specific game files
================================================================================
Translates a single file from a PC game with all advanced features:
- Engine detection
- Encoding detection
- String classification
- Translation cache

Usage:
  python translate_single_file.py <file_path> <api_key> [target_language]
================================================================================
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.advanced_encoding_detector import detect_encoding_advanced
from core.string_classifier import StringClassifier
from core.pc_translation_cache import translate_with_cache


def translate_file(file_path: str, api_key: str, target_language: str = "Portuguese (Brazil)"):
    """
    Translates a single file with advanced features.

    Args:
        file_path: Path to file to translate
        api_key: Gemini API key
        target_language: Target language for translation
    """

    print("\n" + "="*70)
    print("📝 SINGLE FILE TRANSLATOR")
    print("="*70)
    print(f"\n📂 File: {file_path}")
    print(f"🌍 Target: {target_language}")

    if not os.path.exists(file_path):
        print(f"\n❌ Error: File not found: {file_path}")
        return

    # =========================================================================
    # STEP 1: Encoding Detection
    # =========================================================================
    print("\n1️⃣ Detecting encoding...")

    try:
        encoding_result = detect_encoding_advanced(file_path)
        print(f"   ✅ Encoding: {encoding_result.encoding}")
        print(f"   📊 Confidence: {encoding_result.confidence:.0%}")

        if encoding_result.is_custom:
            print(f"   🔧 Custom charset detected ({len(encoding_result.custom_charset)} entries)")
    except Exception as e:
        print(f"   ⚠️  Could not detect encoding: {e}")
        encoding_result = None

    # =========================================================================
    # STEP 2: Read File
    # =========================================================================
    print("\n2️⃣ Reading file...")

    try:
        # Try detected encoding first
        if encoding_result and not encoding_result.is_custom:
            try:
                with open(file_path, 'r', encoding=encoding_result.encoding, errors='ignore') as f:
                    lines = f.readlines()
            except:
                # Fallback to UTF-8
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
        else:
            # Binary/custom charset - read as bytes and try to decode
            with open(file_path, 'rb') as f:
                data = f.read()

            # Try common encodings
            for enc in ['utf-8', 'windows-1252', 'cp850', 'latin-1']:
                try:
                    text = data.decode(enc, errors='ignore')
                    lines = text.split('\n')
                    break
                except:
                    continue

        print(f"   ✅ Read {len(lines)} lines")

    except Exception as e:
        print(f"   ❌ Failed to read file: {e}")
        return

    # =========================================================================
    # STEP 3: Extract Translatable Texts
    # =========================================================================
    print("\n3️⃣ Extracting translatable texts...")

    # Filter empty lines and clean
    texts = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 2:  # Skip very short lines
            texts.append(line)

    print(f"   ✅ Found {len(texts)} non-empty lines")

    # =========================================================================
    # STEP 4: Classify Strings
    # =========================================================================
    print("\n4️⃣ Classifying strings...")

    classifier = StringClassifier()

    translatable_texts = []
    code_filtered = 0

    for text in texts:
        classification = classifier.classify(text, context=file_path)

        if classification.translatable:
            translatable_texts.append(text)
        else:
            code_filtered += 1

    print(f"   ✅ Translatable: {len(translatable_texts)}")
    print(f"   ❌ Filtered (code): {code_filtered}")

    if len(translatable_texts) == 0:
        print("\n⚠️  No translatable texts found!")
        return

    # =========================================================================
    # STEP 5: Translation
    # =========================================================================
    print("\n5️⃣ Translating...")
    print(f"   💰 Estimated cost: ${len(translatable_texts) * 0.005:.2f}")

    # Confirm before proceeding
    confirm = input("\n   ⚠️  Proceed with translation? (yes/no): ")
    if confirm.lower() != "yes":
        print("\n❌ Translation cancelled by user")
        return

    try:
        # Use cache-enabled translation
        cache_file = Path(file_path).parent / "translation_cache.json"

        translations, stats = translate_with_cache(
            texts=translatable_texts,
            api_key=api_key,
            target_language=target_language,
            cache_file=str(cache_file)
        )

        print(f"\n   ✅ Translation completed!")
        print(f"   📊 Cache hits: {stats['cached']}")
        print(f"   📊 API calls: {stats['api_calls']}")
        print(f"   📊 Cache hit rate: {stats['cache_hit_rate']:.1f}%")

    except Exception as e:
        print(f"\n   ❌ Translation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # =========================================================================
    # STEP 6: Save Results
    # =========================================================================
    print("\n6️⃣ Saving results...")

    # Create output filename
    output_file = Path(file_path).parent / f"{Path(file_path).stem}_translated_pt.txt"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f"# Translation of: {Path(file_path).name}\n")
            f.write(f"# Target language: {target_language}\n")
            f.write(f"# Total texts: {len(translatable_texts)}\n")
            f.write(f"# Cache hits: {stats['cached']}\n")
            f.write(f"# API calls: {stats['api_calls']}\n")
            f.write("#" + "="*68 + "\n\n")

            # Write translations
            for i, (original, translated) in enumerate(zip(translatable_texts, translations), 1):
                f.write(f"[{i:05d}] ORIGINAL:\n{original}\n\n")
                f.write(f"[{i:05d}] TRANSLATED:\n{translated}\n\n")
                f.write("-" * 70 + "\n\n")

        print(f"   ✅ Saved to: {output_file}")

    except Exception as e:
        print(f"   ❌ Failed to save: {e}")
        return

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*70)
    print("✅ TRANSLATION COMPLETE")
    print("="*70)
    print(f"\n📊 Statistics:")
    print(f"   Total lines: {len(lines)}")
    print(f"   Non-empty: {len(texts)}")
    print(f"   Translatable: {len(translatable_texts)}")
    print(f"   Filtered: {code_filtered}")
    print(f"   Translated: {len(translations)}")
    print(f"\n💰 Cost:")
    print(f"   API calls: {stats['api_calls']}")
    print(f"   Cached: {stats['cached']}")
    print(f"   Estimated cost: ${stats['api_calls'] * 0.005:.2f}")
    print(f"\n📄 Output: {output_file}")


def main():
    """Main entry point."""

    if len(sys.argv) < 3:
        print("\n" + "="*70)
        print("📝 SINGLE FILE TRANSLATOR")
        print("="*70)
        print("\nUsage:")
        print("  python translate_single_file.py <file_path> <api_key> [target_language]")
        print("\nExample:")
        print("  python translate_single_file.py \"G:\\Game\\files\\main.bin\" \"AIza...\" \"Portuguese (Brazil)\"")
        print("\nFeatures:")
        print("  • Auto-detects encoding")
        print("  • Filters code from text")
        print("  • Uses translation cache")
        print("  • Saves side-by-side comparison")
        sys.exit(1)

    file_path = sys.argv[1]
    api_key = sys.argv[2]
    target_language = sys.argv[3] if len(sys.argv) > 3 else "Portuguese (Brazil)"

    try:
        translate_file(file_path, api_key, target_language)
    except KeyboardInterrupt:
        print("\n\n⚠️  Translation interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
