# -*- coding: utf-8 -*-
"""
================================================================================
TEST ADVANCED MODULES - Examples and Integration Tests
================================================================================
Demonstrates how to use the 3 new advanced modules:
1. Engine Fingerprinting
2. String Classifier
3. Advanced Encoding Detector

Run this to verify modules are working correctly.
================================================================================
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine_fingerprinting import detect_engine, EngineType
from core.string_classifier import classify_string, StringType
from core.advanced_encoding_detector import detect_encoding_advanced


def test_engine_fingerprinting():
    """Test engine detection with various examples."""
    print("\n" + "="*70)
    print("🔍 TESTING ENGINE FINGERPRINTING")
    print("="*70)

    # Test cases
    test_cases = [
        ("C:\\Games\\UnityGame", "Unity game directory"),
        ("C:\\Games\\RPGMaker\\www", "RPG Maker MV game"),
        ("game.smc", "SNES ROM file"),
        ("game.nes", "NES ROM file"),
        ("C:\\Games\\UnrealGame", "Unreal Engine game"),
    ]

    for path, description in test_cases:
        print(f"\n📂 Testing: {description}")
        print(f"   Path: {path}")

        try:
            result = detect_engine(path)

            print(f"   ✅ Engine: {result.engine.value}")
            print(f"   📊 Confidence: {result.confidence:.1%}")
            if result.version:
                print(f"   🏷️  Version: {result.version}")
            if result.signatures_found:
                print(f"   🔑 Signatures: {', '.join(result.signatures_found[:3])}")

        except FileNotFoundError:
            print(f"   ⚠️  File/directory not found (expected for this test)")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def test_string_classifier():
    """Test string classification with various examples."""
    print("\n" + "="*70)
    print("🏷️  TESTING STRING CLASSIFIER")
    print("="*70)

    # Test cases: (text, context, expected_type)
    test_cases = [
        ("Welcome to the game!", None, StringType.STATIC),
        ("Hello {player_name}!", None, StringType.TEMPLATE),
        ("player_health_max", None, StringType.CODE),
        ("Score: %d points", None, StringType.TEMPLATE),
        ("C:\\Program Files\\Game", None, StringType.CODE),
        ("Press any key to continue...", "menu.lua", StringType.STATIC),
        ("if score > 0 then 'Winner' end", "script.lua", StringType.MIXED),
        ("#FF0000", None, StringType.CODE),
        ("MAX_PLAYERS", None, StringType.CODE),
        ("Loading...", None, StringType.STATIC),
        ("player.name + ' wins!'", None, StringType.RUNTIME),
        ("New Game", "menu.json", StringType.STATIC),
    ]

    print("\n📋 Test Results:")
    print(f"{'Text':<40} {'Expected':<12} {'Detected':<12} {'Match':<6} {'Translatable'}")
    print("-" * 90)

    correct = 0
    total = len(test_cases)

    for text, context, expected_type in test_cases:
        result = classify_string(text, context)

        match = "✅" if result.type == expected_type else "❌"
        if result.type == expected_type:
            correct += 1

        translatable = "Yes" if result.translatable else "No"

        text_display = text[:38] + ".." if len(text) > 40 else text

        print(f"{text_display:<40} {expected_type.value:<12} {result.type.value:<12} {match:<6} {translatable}")

        # Show placeholders if found
        if result.placeholders:
            print(f"  └─ Placeholders: {', '.join(result.placeholders)}")

    print("-" * 90)
    print(f"Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")


def test_encoding_detector():
    """Test encoding detection with various examples."""
    print("\n" + "="*70)
    print("📝 TESTING ADVANCED ENCODING DETECTOR")
    print("="*70)

    # Test cases: (description, sample_bytes, expected_encoding)
    test_cases = [
        ("UTF-8 with BOM", b'\xef\xbb\xbfHello World', "utf-8-sig"),
        ("UTF-16 LE with BOM", b'\xff\xfeH\x00e\x00l\x00l\x00o\x00', "utf-16-le"),
        ("Plain ASCII", b'Hello World!', "ascii"),
        ("Windows-1252", b'Ol\xe1 Mundo!', "windows-1252"),
        ("SNES ROM header", b'\x00' * 0x7FC0 + b'GAME TITLE  \x00\x00', "custom"),
    ]

    print("\n📋 Test Results:")
    print(f"{'Description':<25} {'Expected':<15} {'Detected':<15} {'Match':<6} {'Custom'}")
    print("-" * 80)

    for description, sample_bytes, expected_encoding in test_cases:
        # Create temporary test file
        test_file = Path("temp_encoding_test.bin")

        try:
            with open(test_file, 'wb') as f:
                f.write(sample_bytes)

            result = detect_encoding_advanced(str(test_file))

            match = "✅" if result.encoding == expected_encoding else "❌"
            custom = "Yes" if result.is_custom else "No"

            print(f"{description:<25} {expected_encoding:<15} {result.encoding:<15} {match:<6} {custom}")

            if result.is_custom and result.custom_charset:
                print(f"  └─ Custom charset: {len(result.custom_charset)} entries")

        except Exception as e:
            print(f"{description:<25} {'ERROR':<15} {str(e)[:15]:<15} {'❌':<6} {'N/A'}")

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()


def test_integration_example():
    """Demonstrate integration of all 3 modules in a real workflow."""
    print("\n" + "="*70)
    print("🔄 INTEGRATION EXAMPLE: Complete Translation Workflow")
    print("="*70)

    game_path = "C:\\Games\\SampleGame"

    print(f"\n📂 Analyzing game: {game_path}")

    # Step 1: Detect engine
    print("\n1️⃣ Detecting game engine...")
    try:
        engine_result = detect_engine(game_path)
        print(f"   ✅ Engine: {engine_result.engine.value}")
        print(f"   📊 Confidence: {engine_result.confidence:.1%}")

        # Adjust extraction strategy based on engine
        if engine_result.engine == EngineType.UNITY:
            print("   💡 Strategy: Focus on .assets and .unity3d files")
        elif engine_result.engine == EngineType.RPG_MAKER_MV:
            print("   💡 Strategy: Extract from www/data/*.json")
        elif engine_result.engine.value.startswith("SNES"):
            print("   💡 Strategy: Use ROM-specific extraction")

    except FileNotFoundError:
        print("   ⚠️  Game path not found (this is a demo)")
        engine_result = None

    # Step 2: Sample texts to classify
    print("\n2️⃣ Classifying extracted strings...")

    sample_texts = [
        "Welcome to the adventure!",
        "player_current_level",
        "Score: {score}",
        "C:\\save\\game.dat",
        "New Game",
    ]

    translatable_count = 0

    for text in sample_texts:
        result = classify_string(text)
        status = "✅ Translate" if result.translatable else "❌ Skip"
        print(f"   {status}: \"{text}\" [{result.type.value}]")

        if result.translatable:
            translatable_count += 1

    print(f"\n   📊 Translatable: {translatable_count}/{len(sample_texts)}")

    # Step 3: Detect encoding
    print("\n3️⃣ Detecting text file encoding...")
    print("   💡 Would detect encoding of game's text files here")
    print("   Example: UTF-8 (97% confidence) or Custom SNES charset")

    print("\n✅ Integration test complete!")
    print("\n💡 In a real workflow, these modules would:")
    print("   • Automatically detect the game engine")
    print("   • Filter out non-translatable strings (code, paths, etc)")
    print("   • Use correct encoding for extraction and reinsertion")
    print("   • Save 50-70% translation time and cost")


def main():
    """Run all tests."""
    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  ADVANCED MODULES TEST SUITE".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)

    try:
        # Run individual tests
        test_engine_fingerprinting()
        test_string_classifier()
        test_encoding_detector()

        # Run integration example
        test_integration_example()

        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)
        print("\n💡 Next steps:")
        print("   1. Test with real game files")
        print("   2. Integrate into pc_pipeline.py")
        print("   3. Test with ROM files")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
