# -*- coding: utf-8 -*-
"""
================================================================================
PIPELINE INTEGRATION EXAMPLE - Advanced Modules + Existing Pipeline
================================================================================
Shows how to integrate the 3 new modules into existing translation pipeline:
1. Engine Fingerprinting → Adjust extraction strategy
2. String Classifier → Filter non-translatable strings
3. Advanced Encoding Detector → Use correct encoding

100% PLUGGABLE - Does not modify existing code.
================================================================================
"""

import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine_fingerprinting import detect_engine, EngineType
from core.string_classifier import StringClassifier, StringType
from core.advanced_encoding_detector import AdvancedEncodingDetector
from core.pc_text_extractor import PCTextExtractor


def enhanced_translation_workflow(game_path: str, api_key: str) -> Dict:
    """
    Complete translation workflow using all advanced modules.

    This is a PLUGGABLE enhancement - does not modify existing pipeline.
    Can be used alongside or instead of standard pipeline.

    Args:
        game_path: Path to game directory or ROM file
        api_key: Gemini API key

    Returns:
        Dictionary with results and statistics
    """

    print("\n" + "="*70)
    print("🚀 ENHANCED TRANSLATION WORKFLOW")
    print("="*70)

    results = {
        'engine': None,
        'total_texts': 0,
        'translatable': 0,
        'filtered_code': 0,
        'encoding': None,
        'success': False
    }

    # =========================================================================
    # STEP 1: ENGINE FINGERPRINTING
    # =========================================================================
    print("\n1️⃣ Detecting game engine...")

    try:
        engine_result = detect_engine(game_path)
        results['engine'] = engine_result.engine.value

        print(f"   ✅ Engine: {engine_result.engine.value}")
        print(f"   📊 Confidence: {engine_result.confidence:.1%}")

        if engine_result.version:
            print(f"   🏷️  Version: {engine_result.version}")

    except Exception as e:
        print(f"   ⚠️  Could not detect engine: {e}")
        print("   💡 Continuing with generic extraction...")
        engine_result = None

    # =========================================================================
    # STEP 2: TEXT EXTRACTION (with engine-specific optimization)
    # =========================================================================
    print("\n2️⃣ Extracting texts...")

    extractor = PCTextExtractor(game_path)

    # Adjust extraction strategy based on detected engine
    if engine_result:
        if engine_result.engine == EngineType.UNITY:
            print("   💡 Unity detected: prioritizing .assets files")
            extractor.set_priority_extensions(['.assets', '.unity3d', '.resource'])

        elif engine_result.engine == EngineType.UNREAL:
            print("   💡 Unreal detected: prioritizing .pak and .uasset files")
            extractor.set_priority_extensions(['.pak', '.uasset', '.umap'])

        elif engine_result.engine == EngineType.RPG_MAKER_MV:
            print("   💡 RPG Maker MV detected: prioritizing www/data/*.json")
            extractor.set_priority_folders(['www/data', 'www/js'])
            extractor.set_priority_extensions(['.json'])

        elif engine_result.engine.value.startswith("SNES"):
            print("   💡 SNES ROM detected: using ROM-specific extraction")
            # Note: Would use ROM-specific extractor here
            print("   ℹ️  For ROMs, use rom_text_extractor instead")

    # Extract texts
    try:
        extractor.extract_all()
        results['total_texts'] = len(extractor.extracted_texts)
        print(f"   ✅ Extracted {results['total_texts']} text entries")

    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        return results

    # =========================================================================
    # STEP 3: ENCODING DETECTION
    # =========================================================================
    print("\n3️⃣ Detecting text encodings...")

    encoding_cache = {}

    for text_entry in extractor.extracted_texts[:10]:  # Sample first 10 files
        file_path = text_entry.file_path

        if file_path not in encoding_cache:
            try:
                detector = AdvancedEncodingDetector(file_path)
                encoding_result = detector.detect()
                encoding_cache[file_path] = encoding_result

                print(f"   📝 {Path(file_path).name}: {encoding_result.encoding} "
                      f"({encoding_result.confidence:.0%})")

            except Exception as e:
                print(f"   ⚠️  {Path(file_path).name}: Could not detect encoding")
                continue

    # Store encoding info in metadata
    for text_entry in extractor.extracted_texts:
        if text_entry.file_path in encoding_cache:
            enc_result = encoding_cache[text_entry.file_path]
            text_entry.metadata['encoding'] = enc_result.encoding
            text_entry.metadata['is_custom_charset'] = enc_result.is_custom

    if encoding_cache:
        most_common = max(set(e.encoding for e in encoding_cache.values()),
                         key=lambda x: sum(1 for e in encoding_cache.values() if e.encoding == x))
        results['encoding'] = most_common
        print(f"   📊 Most common encoding: {most_common}")

    # =========================================================================
    # STEP 4: STRING CLASSIFICATION
    # =========================================================================
    print("\n4️⃣ Classifying strings...")

    classifier = StringClassifier()

    classification_stats = {
        StringType.STATIC: 0,
        StringType.TEMPLATE: 0,
        StringType.RUNTIME: 0,
        StringType.MIXED: 0,
        StringType.CODE: 0,
        StringType.UNKNOWN: 0
    }

    for text_entry in extractor.extracted_texts:
        classification = classifier.classify(
            text=text_entry.original_text,
            context=text_entry.file_path
        )

        # Update statistics
        classification_stats[classification.type] += 1

        # Mark non-translatable strings
        if not classification.translatable:
            text_entry.extractable = False
            results['filtered_code'] += 1
        else:
            results['translatable'] += 1

        # Store classification metadata
        text_entry.metadata['string_type'] = classification.type.value
        text_entry.metadata['classification_confidence'] = classification.confidence

        if classification.placeholders:
            text_entry.metadata['placeholders'] = classification.placeholders

    # Print classification summary
    print(f"\n   📊 Classification Results:")
    print(f"      ✅ STATIC (translatable):    {classification_stats[StringType.STATIC]:4d}")
    print(f"      ✅ TEMPLATE (translatable):  {classification_stats[StringType.TEMPLATE]:4d}")
    print(f"      ⚠️  RUNTIME (check context):  {classification_stats[StringType.RUNTIME]:4d}")
    print(f"      ❌ MIXED (skip):             {classification_stats[StringType.MIXED]:4d}")
    print(f"      ❌ CODE (skip):              {classification_stats[StringType.CODE]:4d}")
    print(f"      ❓ UNKNOWN:                  {classification_stats[StringType.UNKNOWN]:4d}")

    print(f"\n   📈 Summary:")
    print(f"      Total texts: {results['total_texts']}")
    print(f"      Translatable: {results['translatable']} ({results['translatable']/results['total_texts']*100:.1f}%)")
    print(f"      Filtered (code): {results['filtered_code']} ({results['filtered_code']/results['total_texts']*100:.1f}%)")

    # =========================================================================
    # STEP 5: TRANSLATION (with cache)
    # =========================================================================
    print("\n5️⃣ Translating texts...")

    # Get only translatable texts
    translatable_texts = extractor.get_translatable_texts()

    if not translatable_texts:
        print("   ⚠️  No translatable texts found")
        return results

    print(f"   💡 Ready to translate {len(translatable_texts)} texts")
    print(f"   💡 Estimated cost: ${len(translatable_texts) * 0.005:.2f}")

    # NOTE: Actual translation would happen here
    # from core.pc_translation_cache import translate_with_cache
    # translations, stats = translate_with_cache(
    #     texts=[t.original_text for t in translatable_texts],
    #     api_key=api_key,
    #     target_language="Portuguese (Brazil)",
    #     cache_file="translation_cache.json"
    # )

    print("   ℹ️  (Translation skipped in this example)")

    # =========================================================================
    # STEP 6: RESULTS
    # =========================================================================
    print("\n" + "="*70)
    print("✅ WORKFLOW COMPLETE")
    print("="*70)

    results['success'] = True

    print(f"\n📊 Final Statistics:")
    print(f"   Engine: {results['engine'] or 'Unknown'}")
    print(f"   Encoding: {results['encoding'] or 'Mixed'}")
    print(f"   Total texts: {results['total_texts']}")
    print(f"   Translatable: {results['translatable']}")
    print(f"   Filtered (code/runtime): {results['filtered_code']}")
    print(f"   Success rate: {results['translatable']/results['total_texts']*100:.1f}%")

    return results


def compare_with_without_advanced_modules(game_path: str):
    """
    Compare results WITH and WITHOUT advanced modules.
    Shows the improvement in filtering accuracy.
    """

    print("\n" + "="*70)
    print("📊 COMPARISON: Standard vs Enhanced Pipeline")
    print("="*70)

    # Standard extraction (without advanced modules)
    print("\n❌ Standard Pipeline (no filtering):")
    try:
        extractor_standard = PCTextExtractor(game_path)
        extractor_standard.extract_all()

        standard_count = len(extractor_standard.extracted_texts)
        print(f"   Total extracted: {standard_count}")
        print(f"   Translatable: {standard_count} (assumes all)")
        print(f"   False positives: Unknown (might translate code!)")

    except Exception as e:
        print(f"   ⚠️  Could not run standard extraction: {e}")
        standard_count = 0

    # Enhanced extraction (with advanced modules)
    print("\n✅ Enhanced Pipeline (with string classifier):")
    try:
        extractor_enhanced = PCTextExtractor(game_path)
        extractor_enhanced.extract_all()

        classifier = StringClassifier()
        translatable = 0

        for entry in extractor_enhanced.extracted_texts:
            classification = classifier.classify(entry.original_text, entry.file_path)
            if classification.translatable:
                translatable += 1

        enhanced_total = len(extractor_enhanced.extracted_texts)
        filtered = enhanced_total - translatable

        print(f"   Total extracted: {enhanced_total}")
        print(f"   Translatable: {translatable}")
        print(f"   Filtered (code): {filtered}")

        if standard_count > 0:
            improvement = (filtered / standard_count * 100)
            print(f"\n   💡 Improvement: Filtered {improvement:.1f}% of false positives")
            print(f"   💰 Cost savings: ${filtered * 0.005:.2f} per translation run")

    except Exception as e:
        print(f"   ⚠️  Could not run enhanced extraction: {e}")


def main():
    """Run example workflow."""

    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  PIPELINE INTEGRATION EXAMPLE".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)

    # Example game path (user should replace with actual path)
    game_path = "C:\\Games\\SampleGame"
    api_key = "YOUR_API_KEY_HERE"

    print("\n💡 This example demonstrates integration of advanced modules")
    print("   Replace 'game_path' with actual game directory or ROM file")
    print()

    # Run enhanced workflow
    try:
        results = enhanced_translation_workflow(game_path, api_key)

        if results['success']:
            print("\n✅ Example completed successfully")
        else:
            print("\n⚠️  Example completed with warnings")

    except FileNotFoundError:
        print("\n⚠️  Game path not found - this is expected for the demo")
        print("\n💡 To use this script:")
        print("   1. Replace 'game_path' with your actual game directory")
        print("   2. Replace 'api_key' with your Gemini API key")
        print("   3. Run: python pipeline_integration_example.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Show comparison
    print("\n" + "="*70)
    try:
        compare_with_without_advanced_modules(game_path)
    except FileNotFoundError:
        print("\n⚠️  Comparison skipped (game path not found)")

    print("\n" + "="*70)
    print("📚 INTEGRATION GUIDE")
    print("="*70)
    print("""
To integrate these modules into your existing pipeline:

1. ENGINE FINGERPRINTING:
   from core.engine_fingerprinting import detect_engine
   engine = detect_engine(game_path)
   # Use engine info to adjust extraction strategy

2. STRING CLASSIFIER:
   from core.string_classifier import StringClassifier
   classifier = StringClassifier()
   result = classifier.classify(text, context)
   if not result.translatable:
       skip_translation()

3. ADVANCED ENCODING:
   from core.advanced_encoding_detector import detect_encoding_advanced
   encoding = detect_encoding_advanced(file_path)
   # Use encoding.encoding for file operations

All modules are 100% optional and pluggable!
""")


if __name__ == "__main__":
    main()
