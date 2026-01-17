#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HYBRID EXTRACTOR - Unificação V9 + Fast Clean
==============================================
Combina Profile B (DTE/MTE) com ASCII puro para máxima compatibilidade.

Estratégia Adaptativa:
1. Tenta Profile B (DTE/MTE) primeiro
2. Se falhar, usa ASCII puro
3. Unifica e filtra resultados

Autor: NeuroROM AI V6
Data: 2025-01
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Importa os dois extractors
try:
    from ultimate_extractor_v9 import UltimateExtractorV9
    from fast_clean_extractor import FastCleanExtractor
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ultimate_extractor_v9 import UltimateExtractorV9
    from fast_clean_extractor import FastCleanExtractor


class HybridExtractor:
    """
    Extrator híbrido que combina:
    - V9 Profile B (para RPGs com DTE/MTE)
    - Fast Clean (para jogos action com ASCII)
    """

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = None

        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM não encontrada: {rom_path}")

        # Carrega ROM
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

    def _calculate_entropy(self, data: bytes) -> float:
        """Calcula entropia Shannon para detectar compressão"""
        if not data:
            return 0.0

        from collections import Counter
        import math

        counter = Counter(data)
        entropy = 0.0
        length = len(data)

        for count in counter.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy

    def _detect_best_method(self) -> str:
        """
        Detecta qual método usar baseado em características da ROM

        Returns:
            'profile_b': RPG com DTE/MTE provável
            'ascii': Action game com ASCII puro
            'hybrid': Combinar ambos
        """
        # Amostra de 64KB para análise
        sample_size = min(65536, len(self.rom_data))
        sample = bytes(self.rom_data[:sample_size])

        # Calcula entropia
        entropy = self._calculate_entropy(sample)

        # Procura por padrões ASCII
        ascii_pattern = re.compile(b'[\x20-\x7E]{10,}')
        ascii_matches = len(ascii_pattern.findall(sample))

        # Procura por palavras inglesas comuns
        common_words = [b'the ', b'and ', b'you ', b'are ', b'have ', b'will ']
        word_count = sum(sample.count(word) for word in common_words)

        print(f"\n🔍 Análise Adaptativa:")
        print(f"   • Entropia: {entropy:.2f}")
        print(f"   • Padrões ASCII: {ascii_matches}")
        print(f"   • Palavras inglesas: {word_count}")

        # Decisão
        if entropy > 6.0 and word_count > 5:
            print(f"   ✅ Método: PROFILE B (RPG detectado)")
            return 'profile_b'
        elif ascii_matches > 20 and word_count > 10:
            print(f"   ✅ Método: ASCII PURO (Action game detectado)")
            return 'ascii'
        else:
            print(f"   ✅ Método: HÍBRIDO (combinar ambos)")
            return 'hybrid'

    def _extract_with_profile_b(self) -> List[Dict]:
        """Extrai usando Profile B (V9)"""
        print(f"\n🎮 Executando Profile B (V9 FORENSIC)...")

        try:
            extractor = UltimateExtractorV9(str(self.rom_path))

            # Extrai apenas método principal
            texts = extractor.extract_profile_b_dictionary()

            print(f"   ✅ Profile B: {len(texts)} strings")
            return texts

        except Exception as e:
            print(f"   ⚠️ Profile B falhou: {e}")
            return []

    def _extract_with_ascii(self) -> List[Dict]:
        """Extrai usando ASCII puro (Fast Clean)"""
        print(f"\n📝 Executando ASCII Fast Clean...")

        try:
            extractor = FastCleanExtractor(str(self.rom_path))
            raw_strings = extractor.extract_ascii_strings()

            # Filtra com SuperTextFilter
            filtered = extractor.text_filter.filter_bulk(raw_strings)

            # Converte para formato padrão
            texts = [
                {
                    'offset': offset,
                    'text': text,
                    'source': 'ascii_clean',
                    'length': len(text)
                }
                for offset, text in filtered
            ]

            print(f"   ✅ ASCII Clean: {len(texts)} strings")
            return texts

        except Exception as e:
            print(f"   ⚠️ ASCII Clean falhou: {e}")
            return []

    def extract_all(self, output_path: Optional[str] = None) -> Dict:
        """
        Executa extração híbrida completa

        Args:
            output_path: Caminho do arquivo de saída

        Returns:
            Estatísticas da extração
        """
        print(f"\n{'='*70}")
        print(f"🔥 HYBRID EXTRACTOR - Adaptive Extraction")
        print(f"{'='*70}")
        print(f"ROM: {self.rom_path.name}")
        print(f"Tamanho: {len(self.rom_data):,} bytes")

        all_texts = []
        stats = {
            'method': '',
            'profile_b': 0,
            'ascii_clean': 0,
            'total_raw': 0,
            'total_unique': 0
        }

        # Detecta melhor método
        method = self._detect_best_method()
        stats['method'] = method

        # Extrai conforme método
        if method == 'profile_b':
            profile_texts = self._extract_with_profile_b()
            all_texts.extend(profile_texts)
            stats['profile_b'] = len(profile_texts)

        elif method == 'ascii':
            ascii_texts = self._extract_with_ascii()
            all_texts.extend(ascii_texts)
            stats['ascii_clean'] = len(ascii_texts)

        else:  # hybrid
            profile_texts = self._extract_with_profile_b()
            ascii_texts = self._extract_with_ascii()

            all_texts.extend(profile_texts)
            all_texts.extend(ascii_texts)

            stats['profile_b'] = len(profile_texts)
            stats['ascii_clean'] = len(ascii_texts)

        stats['total_raw'] = len(all_texts)

        # Remove duplicatas por offset
        unique_texts = {}
        for item in all_texts:
            offset = item['offset']
            if offset not in unique_texts:
                unique_texts[offset] = item
            else:
                # Prefere ASCII se ambos existem
                if item.get('source') == 'ascii_clean':
                    unique_texts[offset] = item

        all_texts = list(unique_texts.values())
        stats['total_unique'] = len(all_texts)

        # Define output path
        if output_path is None:
            output_path = self.rom_path.parent / f"{self.rom_path.stem}_HYBRID.txt"
        else:
            output_path = Path(output_path)

        # Salva arquivo
        print(f"\n💾 Salvando resultado...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# HYBRID EXTRACTOR - Profile B + ASCII Clean\n")
            f.write("# " + "="*68 + "\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Método adaptativo: {method.upper()}\n")
            f.write(f"# Profile B strings: {stats['profile_b']}\n")
            f.write(f"# ASCII Clean strings: {stats['ascii_clean']}\n")
            f.write(f"# Total único: {stats['total_unique']}\n")
            f.write("# " + "="*68 + "\n\n")

            for item in sorted(all_texts, key=lambda x: x['offset']):
                source_tag = ""

                if item.get('source') == 'ascii_clean':
                    source_tag = " 📝"
                elif 'profile_b' in item.get('source', ''):
                    source_tag = " 🎮"

                f.write(f"[0x{item['offset']:X}]{source_tag} {item['text']}\n")

        # Relatório final
        print(f"\n{'='*70}")
        print(f"✅ EXTRAÇÃO HÍBRIDA CONCLUÍDA!")
        print(f"{'='*70}")
        print(f"📊 Estatísticas:")
        print(f"   🎮 Profile B (DTE/MTE): {stats['profile_b']} strings")
        print(f"   📝 ASCII Clean: {stats['ascii_clean']} strings")
        print(f"   📚 Total bruto: {stats['total_raw']}")
        print(f"   ✨ Total único: {stats['total_unique']}")
        print(f"   💾 Arquivo: {output_path}")
        print(f"{'='*70}\n")

        return stats


def main():
    """CLI Interface"""
    import sys

    if len(sys.argv) < 2:
        print("="*70)
        print("  HYBRID EXTRACTOR - Profile B + ASCII Clean")
        print("="*70)
        print()
        print("Uso:")
        print(f"  python {Path(__file__).name} <rom_file> [output.txt]")
        print()
        print("Exemplos:")
        print(f"  python {Path(__file__).name} game.smc")
        print(f"  python {Path(__file__).name} game.smc custom_output.txt")
        print()
        return 1

    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        extractor = HybridExtractor(rom_path)
        stats = extractor.extract_all(output_path)
        return 0

    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
