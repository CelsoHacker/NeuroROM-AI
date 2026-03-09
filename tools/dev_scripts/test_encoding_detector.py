#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
TEST ENCODING DETECTOR - Validação com Arquivos Reais
================================================================================
Testa o encoding_detector.py com diferentes tipos de arquivos:
1. Cria arquivos de teste com encodings conhecidos
2. Detecta encoding automaticamente
3. Valida se detecção está correta
4. Testa com arquivos reais de jogo (se fornecidos)
================================================================================
"""

import sys
import os
from pathlib import Path
import tempfile

# Adiciona core ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.encoding_detector import EncodingDetector, batch_detect_encodings


def create_test_files(test_dir: Path) -> dict:
    """
    Cria arquivos de teste com encodings conhecidos.

    Returns:
        Dict {encoding: file_path}
    """
    print(f"\n🔧 CREATING TEST FILES")
    print(f"{'='*70}")

    test_files = {}

    # Textos de teste em diferentes idiomas
    test_texts = {
        'utf-8': "Hello World! Olá Mundo! こんにちは世界! 你好世界! 안녕하세요!",
        'utf-16-le': "UTF-16 Little Endian: Texto com acentuação",
        'utf-16-be': "UTF-16 Big Endian: Test file",
        'windows-1252': "Windows-1252: Café, naïve, résumé",
        'iso-8859-1': "ISO-8859-1 (Latin-1): Ação, São Paulo, coração",
        'utf-8-sig': "UTF-8 with BOM: Arquivo com marcador de ordem de bytes",
    }

    for encoding, text in test_texts.items():
        file_path = test_dir / f"test_{encoding.replace('-', '_')}.txt"

        try:
            # Cria arquivo com encoding específico
            if encoding == 'utf-8-sig':
                # UTF-8 com BOM
                with open(file_path, 'wb') as f:
                    f.write(b'\xef\xbb\xbf')  # BOM
                    f.write(text.encode('utf-8'))
            else:
                with open(file_path, 'w', encoding=encoding) as f:
                    f.write(text)

            test_files[encoding] = str(file_path)
            print(f"  ✓ Created: {file_path.name} ({encoding})")

        except Exception as e:
            print(f"  ✗ Failed to create {encoding}: {e}")

    print(f"{'='*70}\n")

    return test_files


def test_detection_accuracy(test_files: dict):
    """
    Testa precisão da detecção comparando com encoding esperado.

    Args:
        test_files: Dict {expected_encoding: file_path}
    """
    print(f"\n🎯 TESTING DETECTION ACCURACY")
    print(f"{'='*70}")

    results = {
        'total': 0,
        'correct': 0,
        'correct_family': 0,  # UTF-8 vs utf-8-sig = mesma família
        'incorrect': 0,
        'details': []
    }

    for expected_encoding, file_path in test_files.items():
        results['total'] += 1

        detector = EncodingDetector(file_path)
        result = detector.detect()

        # Verifica se detecção está correta
        detected = result.encoding.lower().replace('-', '').replace('_', '')
        expected = expected_encoding.lower().replace('-', '').replace('_', '')

        # Exata
        if detected == expected:
            status = "✓ CORRECT"
            results['correct'] += 1
            results['correct_family'] += 1

        # Mesma família (ex: utf-8 vs utf-8-sig)
        elif (detected.startswith('utf8') and expected.startswith('utf8')) or \
             (detected.startswith('utf16') and expected.startswith('utf16')):
            status = "≈ FAMILY"
            results['correct_family'] += 1

        else:
            status = "✗ WRONG"
            results['incorrect'] += 1

        details = {
            'file': Path(file_path).name,
            'expected': expected_encoding,
            'detected': result.encoding,
            'confidence': result.confidence,
            'validated': result.validated,
            'status': status
        }

        results['details'].append(details)

        print(f"  {status:10s} | {Path(file_path).name:35s} | "
              f"Expected: {expected_encoding:15s} → Detected: {result.encoding:15s} "
              f"(conf: {result.confidence:.2f})")

    # Sumário
    accuracy_exact = (results['correct'] / results['total'] * 100) if results['total'] > 0 else 0
    accuracy_family = (results['correct_family'] / results['total'] * 100) if results['total'] > 0 else 0

    print(f"\n{'='*70}")
    print(f"ACCURACY SUMMARY:")
    print(f"  Total files: {results['total']}")
    print(f"  Exact matches: {results['correct']} ({accuracy_exact:.1f}%)")
    print(f"  Family matches: {results['correct_family']} ({accuracy_family:.1f}%)")
    print(f"  Incorrect: {results['incorrect']}")
    print(f"{'='*70}\n")

    return results


def test_with_game_files(game_dir: str):
    """
    Testa com arquivos reais de um jogo.

    Args:
        game_dir: Diretório do jogo
    """
    print(f"\n🎮 TESTING WITH REAL GAME FILES")
    print(f"{'='*70}")
    print(f"Game directory: {game_dir}\n")

    game_path = Path(game_dir)
    if not game_path.exists():
        print(f"❌ Directory not found: {game_dir}")
        return

    # Busca arquivos de texto no jogo
    text_extensions = {'.txt', '.json', '.xml', '.ini', '.cfg', '.lua', '.log'}
    game_files = []

    for ext in text_extensions:
        game_files.extend(game_path.rglob(f'*{ext}'))

    if not game_files:
        print(f"⚠️  No text files found in {game_dir}")
        return

    # Limita a 20 arquivos para teste
    game_files = game_files[:20]

    print(f"Found {len(game_files)} text files. Testing...\n")

    # Detecta encodings
    file_paths = [str(f) for f in game_files]
    results = batch_detect_encodings(file_paths)

    # Análise dos resultados
    encodings_found = {}
    low_confidence = []

    for file_path, result in results.items():
        # Conta encodings
        enc = result.encoding
        encodings_found[enc] = encodings_found.get(enc, 0) + 1

        # Detecta baixa confiança
        if result.confidence < 0.7 or not result.validated:
            low_confidence.append((Path(file_path).name, result))

    # Sumário
    print(f"\n📊 GAME FILES SUMMARY:")
    print(f"{'='*70}")
    print(f"Encodings detected:")
    for enc, count in sorted(encodings_found.items(), key=lambda x: x[1], reverse=True):
        print(f"  {enc:20s}: {count:3d} files")

    if low_confidence:
        print(f"\n⚠️  LOW CONFIDENCE DETECTIONS ({len(low_confidence)} files):")
        for filename, result in low_confidence[:10]:  # Top 10
            print(f"  {filename:40s} → {result.encoding:15s} "
                  f"(conf: {result.confidence:.2f}, validated: {result.validated})")

    print(f"{'='*70}\n")


def test_round_trip(test_files: dict):
    """
    Testa round-trip: read → write → read novamente.

    Args:
        test_files: Dict de arquivos de teste
    """
    print(f"\n🔄 TESTING ROUND-TRIP (READ → WRITE → READ)")
    print(f"{'='*70}")

    temp_dir = Path(tempfile.gettempdir()) / 'encoding_test_roundtrip'
    temp_dir.mkdir(exist_ok=True)

    success_count = 0
    total_count = 0

    for encoding, original_file in list(test_files.items())[:3]:  # Testa 3 arquivos
        total_count += 1

        try:
            # 1. Detecta encoding
            detector = EncodingDetector(original_file)
            result = detector.detect()

            # 2. Lê arquivo
            content, _ = detector.read_file()

            if content is None:
                print(f"  ✗ {Path(original_file).name}: Failed to read")
                continue

            # 3. Escreve em novo arquivo com MESMO encoding
            output_file = temp_dir / f"roundtrip_{Path(original_file).name}"

            # Remove BOM se houver (para comparação justa)
            write_encoding = result.encoding.replace('-sig', '')

            with open(output_file, 'w', encoding=write_encoding) as f:
                f.write(content)

            # 4. Lê novamente
            detector2 = EncodingDetector(str(output_file))
            result2 = detector2.detect()
            content2, _ = detector2.read_file()

            # 5. Compara
            if content == content2:
                print(f"  ✓ {Path(original_file).name}: Round-trip SUCCESS "
                      f"({result.encoding} → {result2.encoding})")
                success_count += 1
            else:
                print(f"  ✗ {Path(original_file).name}: Content mismatch!")

        except Exception as e:
            print(f"  ✗ {Path(original_file).name}: Error: {e}")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\n{'='*70}")
    print(f"Round-trip success rate: {success_count}/{total_count} "
          f"({success_count/total_count*100:.1f}%)")
    print(f"{'='*70}\n")


def main():
    """Executa todos os testes."""
    print(f"\n{'='*70}")
    print(f"ENCODING DETECTOR - COMPREHENSIVE TEST SUITE")
    print(f"{'='*70}\n")

    # Cria diretório temporário para testes
    test_dir = Path(tempfile.gettempdir()) / 'encoding_test'
    test_dir.mkdir(exist_ok=True)

    try:
        # 1. Cria arquivos de teste
        test_files = create_test_files(test_dir)

        # 2. Testa precisão de detecção
        accuracy_results = test_detection_accuracy(test_files)

        # 3. Testa round-trip
        test_round_trip(test_files)

        # 4. Se fornecido, testa com jogo real
        if len(sys.argv) > 1:
            game_dir = sys.argv[1]
            test_with_game_files(game_dir)
        else:
            print(f"\n💡 TIP: Run with game directory to test real files:")
            print(f"   python test_encoding_detector.py \"C:\\Path\\To\\Game\"")

        # Resultado final
        print(f"\n{'='*70}")
        print(f"✅ ALL TESTS COMPLETED")
        print(f"{'='*70}\n")

        # Retorna código de sucesso baseado na precisão
        exact_accuracy = (accuracy_results['correct'] / accuracy_results['total'] * 100)
        return 0 if exact_accuracy >= 70 else 1

    finally:
        # Cleanup
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
