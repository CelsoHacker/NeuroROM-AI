# -*- coding: utf-8 -*-
"""
================================================================================
GENERIC PC GAME ANALYZER - Universal Game Analysis Tool
================================================================================
Analyzes ANY PC game directory to:
1. Detect game engine
2. Find text files and encodings
3. Classify strings (translatable vs code)
4. Estimate translation workload

100% GENERIC - Works with any game, no hardcoded references.
================================================================================
"""

import sys
import os
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine_fingerprinting import detect_engine
from core.advanced_encoding_detector import detect_encoding_advanced
from core.string_classifier import StringClassifier
from core.pc_text_extractor import PCTextExtractor


def analyze_game_directory(game_path: str) -> Dict:
    """
    Analyzes a PC game directory comprehensively.

    Args:
        game_path: Path to game installation directory

    Returns:
        Dictionary with complete analysis results
    """

    print("\n" + "="*70)
    print("🎮 GENERIC PC GAME ANALYZER")
    print("="*70)
    print(f"\n📂 Analyzing: {game_path}")

    results = {
        'game_path': game_path,
        'engine': None,
        'files_found': 0,
        'text_files': [],
        'binary_files': [],
        'encodings': {},
        'total_texts': 0,
        'translatable': 0,
        'code_filtered': 0,
        'success': False
    }

    # =========================================================================
    # STEP 1: Directory Structure Analysis
    # =========================================================================
    print("\n1️⃣ Analyzing directory structure...")

    if not os.path.exists(game_path):
        print(f"   ❌ Directory not found: {game_path}")
        return results

    # Count files
    all_files = []
    for root, dirs, files in os.walk(game_path):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.append(file_path)

    results['files_found'] = len(all_files)
    print(f"   ✅ Found {len(all_files)} files")

    # Categorize files
    text_extensions = ['.txt', '.json', '.xml', '.ini', '.cfg', '.lua', '.js']
    binary_extensions = ['.bin', '.dat', '.pak', '.assets', '.resource']

    for file_path in all_files:
        ext = Path(file_path).suffix.lower()
        if ext in text_extensions:
            results['text_files'].append(file_path)
        elif ext in binary_extensions:
            results['binary_files'].append(file_path)

    print(f"   📝 Text files: {len(results['text_files'])}")
    print(f"   📦 Binary files: {len(results['binary_files'])}")

    # =========================================================================
    # STEP 2: Engine Detection
    # =========================================================================
    print("\n2️⃣ Detecting game engine...")

    try:
        engine_result = detect_engine(game_path)
        results['engine'] = engine_result.engine.value

        print(f"   ✅ Engine: {engine_result.engine.value}")
        print(f"   📊 Confidence: {engine_result.confidence:.1%}")

        if engine_result.version:
            print(f"   🏷️  Version: {engine_result.version}")

        if engine_result.signatures_found:
            print(f"   🔑 Signatures: {', '.join(engine_result.signatures_found[:3])}")

    except Exception as e:
        print(f"   ⚠️  Could not detect engine: {e}")
        results['engine'] = "Unknown"

    # =========================================================================
    # STEP 3: Encoding Detection (sample files)
    # =========================================================================
    print("\n3️⃣ Detecting file encodings...")

    # Sample up to 10 files for encoding detection
    sample_files = (results['text_files'][:5] + results['binary_files'][:5])

    for file_path in sample_files:
        try:
            detector_result = detect_encoding_advanced(file_path)

            file_name = Path(file_path).name
            results['encodings'][file_name] = {
                'encoding': detector_result.encoding,
                'confidence': detector_result.confidence,
                'is_custom': detector_result.is_custom
            }

            icon = "📝" if not detector_result.is_custom else "🔧"
            print(f"   {icon} {file_name[:40]:<40} {detector_result.encoding:<15} "
                  f"({detector_result.confidence:.0%})")

        except Exception as e:
            print(f"   ⚠️  {Path(file_path).name}: Could not detect encoding")

    # =========================================================================
    # STEP 4: Text Extraction
    # =========================================================================
    print("\n4️⃣ Extracting texts...")

    try:
        extractor = PCTextExtractor(game_path)

        # Set priority based on detected engine
        if results['engine'] == "Unity":
            extractor.set_priority_extensions(['.assets', '.unity3d', '.resource'])
        elif results['engine'] == "Unreal Engine":
            extractor.set_priority_extensions(['.pak', '.uasset', '.umap'])
        elif "RPG Maker" in results['engine']:
            extractor.set_priority_folders(['www/data', 'data'])
            extractor.set_priority_extensions(['.json'])

        extractor.extract_all()

        results['total_texts'] = len(extractor.extracted_texts)
        print(f"   ✅ Extracted {results['total_texts']} text entries")

        # =========================================================================
        # STEP 5: String Classification
        # =========================================================================
        print("\n5️⃣ Classifying strings...")

        classifier = StringClassifier()

        classification_stats = {
            'STATIC': 0,
            'TEMPLATE': 0,
            'RUNTIME': 0,
            'MIXED': 0,
            'CODE': 0,
            'UNKNOWN': 0
        }

        for text_entry in extractor.extracted_texts:
            classification = classifier.classify(
                text=text_entry.original_text,
                context=text_entry.file_path
            )

            classification_stats[classification.type.value.upper()] += 1

            if classification.translatable:
                results['translatable'] += 1
            else:
                results['code_filtered'] += 1

        print(f"\n   📊 Classification Results:")
        print(f"      ✅ STATIC (translatable):    {classification_stats['STATIC']:4d}")
        print(f"      ✅ TEMPLATE (translatable):  {classification_stats['TEMPLATE']:4d}")
        print(f"      ⚠️  RUNTIME (check context):  {classification_stats['RUNTIME']:4d}")
        print(f"      ❌ MIXED (skip):             {classification_stats['MIXED']:4d}")
        print(f"      ❌ CODE (skip):              {classification_stats['CODE']:4d}")
        print(f"      ❓ UNKNOWN:                  {classification_stats['UNKNOWN']:4d}")

        results['success'] = True

    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # STEP 6: Summary & Recommendations
    # =========================================================================
    print("\n" + "="*70)
    print("📊 ANALYSIS SUMMARY")
    print("="*70)

    print(f"\n🎮 Game Information:")
    print(f"   Engine: {results['engine']}")
    print(f"   Total files: {results['files_found']}")
    print(f"   Text files: {len(results['text_files'])}")
    print(f"   Binary files: {len(results['binary_files'])}")

    if results['total_texts'] > 0:
        print(f"\n📝 Text Analysis:")
        print(f"   Total texts extracted: {results['total_texts']}")
        print(f"   Translatable: {results['translatable']} "
              f"({results['translatable']/results['total_texts']*100:.1f}%)")
        print(f"   Filtered (code/runtime): {results['code_filtered']} "
              f"({results['code_filtered']/results['total_texts']*100:.1f}%)")

        # Estimate cost
        estimated_cost = results['translatable'] * 0.005
        print(f"\n💰 Translation Estimate:")
        print(f"   Texts to translate: {results['translatable']}")
        print(f"   Estimated API cost: ${estimated_cost:.2f}")
        print(f"   With cache (2nd run): ${estimated_cost * 0.05:.2f} (95% savings)")

    print("\n💡 Recommendations:")

    if results['engine'] == "Unity":
        print("   • Focus on .assets and .unity3d files")
        print("   • Use UnityEx or AssetStudio for advanced extraction")
    elif results['engine'] == "Unreal Engine":
        print("   • Focus on .pak files")
        print("   • Consider using UnrealPak tool for unpacking")
    elif "RPG Maker" in results['engine']:
        print("   • Check www/data/*.json files for dialogue")
        print("   • Look for Map*.json and CommonEvents.json")
    elif results['engine'] == "Custom" or results['engine'] == "Unknown":
        print("   • Manual analysis recommended")
        print("   • Check for .bin/.dat files with text data")

    if len(results['binary_files']) > 0:
        print("   • Binary files detected - may contain packed text")
        print("   • Consider hex editor analysis for file formats")

    print("\n✅ Analysis complete!")

    return results


def main():
    """Main entry point."""

    if len(sys.argv) < 2:
        print("\n" + "="*70)
        print("🎮 GENERIC PC GAME ANALYZER")
        print("="*70)
        print("\nUsage:")
        print("  python analyze_pc_game.py <game_directory>")
        print("\nExample:")
        print("  python analyze_pc_game.py \"C:\\Games\\MyGame\"")
        print("  python analyze_pc_game.py \"G:\\MyGame\\files\"")
        print("\nThis tool analyzes ANY PC game to:")
        print("  1. Detect game engine")
        print("  2. Find translatable text files")
        print("  3. Detect encodings")
        print("  4. Classify strings (text vs code)")
        print("  5. Estimate translation workload")
        print("\n100% generic - works with any game!")
        sys.exit(1)

    game_path = sys.argv[1]

    # Verify path exists
    if not os.path.exists(game_path):
        print(f"\n❌ Error: Path not found: {game_path}")
        sys.exit(1)

    # Run analysis
    try:
        results = analyze_game_directory(game_path)

        # Export results to JSON (optional)
        if results['success']:
            import json
            output_file = "game_analysis_report.json"

            # Clean results for JSON export
            export_results = {
                'game_path': results['game_path'],
                'engine': results['engine'],
                'files_found': results['files_found'],
                'text_files_count': len(results['text_files']),
                'binary_files_count': len(results['binary_files']),
                'total_texts': results['total_texts'],
                'translatable': results['translatable'],
                'code_filtered': results['code_filtered'],
                'encodings': results['encodings']
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_results, f, indent=2, ensure_ascii=False)

            print(f"\n📄 Report saved to: {output_file}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
