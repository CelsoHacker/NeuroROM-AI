# -*- coding: utf-8 -*-
"""
================================================================================
UNIVERSAL PIPELINE - Orquestrador do Processo Completo de Tradução
================================================================================
Pipeline integrado que combina todos os módulos de análise automática:
1. ROMAnalyzer → Detecta estrutura da ROM
2. TextScanner → Localiza strings de texto
3. CharsetInference → Descobre tabela de caracteres
4. PointerScanner → Mapeia ponteiros
5. CompressionDetector → Identifica dados comprimidos
6. Translation → Traduz via IA (Gemini)
7. SafeReinserter → Reinsere com validação

Formato de saída universal em JSON para interoperabilidade
================================================================================
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Importa os módulos de análise
from .rom_analyzer import ROMAnalyzer
from .text_scanner import TextScanner
from .charset_inference import CharsetInferenceEngine
from .pointer_scanner import PointerScanner
from .compression_detector import CompressionDetector


class UniversalExtractionPipeline:
    """
    Pipeline completo de extração automática de ROMs.
    """

    def __init__(self, rom_path: str, output_dir: Optional[str] = None):
        """
        Args:
            rom_path: Caminho para arquivo ROM
            output_dir: Diretório para outputs (default: rom_path_output/)
        """
        self.rom_path = Path(rom_path)
        self.output_dir = Path(output_dir) if output_dir else self.rom_path.parent / f"{self.rom_path.stem}_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Resultados de cada etapa
        self.rom_analysis = None
        self.text_candidates = []
        self.charset_tables = []
        self.pointer_tables = []
        self.compressed_regions = []
        self.extracted_texts = []

    def run_full_analysis(self) -> Dict:
        """
        Executa pipeline completo de análise automática.

        Returns:
            Dicionário com todos os resultados consolidados
        """
        print(f"\n{'='*70}")
        print(f"🚀 UNIVERSAL EXTRACTION PIPELINE")
        print(f"{'='*70}")
        print(f"ROM: {self.rom_path.name}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*70}\n")

        # Etapa 1: Análise estrutural da ROM
        print("\n" + "="*70)
        print("STAGE 1: ROM STRUCTURE ANALYSIS")
        print("="*70)
        self._run_rom_analysis()

        # Etapa 2: Detecção de compressão
        print("\n" + "="*70)
        print("STAGE 2: COMPRESSION DETECTION")
        print("="*70)
        self._run_compression_detection()

        # Etapa 3: Varredura de texto
        print("\n" + "="*70)
        print("STAGE 3: TEXT SCANNING")
        print("="*70)
        self._run_text_scanning()

        # Etapa 4: Inferência de charset
        print("\n" + "="*70)
        print("STAGE 4: CHARACTER SET INFERENCE")
        print("="*70)
        self._run_charset_inference()

        # Etapa 5: Detecção de ponteiros
        print("\n" + "="*70)
        print("STAGE 5: POINTER SCANNING")
        print("="*70)
        self._run_pointer_scanning()

        # Etapa 6: Consolidação e exportação
        print("\n" + "="*70)
        print("STAGE 6: CONSOLIDATION & EXPORT")
        print("="*70)
        final_data = self._consolidate_results()
        self._export_universal_format(final_data)

        print(f"\n{'='*70}")
        print(f"✅ PIPELINE COMPLETED SUCCESSFULLY")
        print(f"{'='*70}\n")

        return final_data

    def _run_rom_analysis(self):
        """Etapa 1: Análise estrutural."""
        analyzer = ROMAnalyzer(str(self.rom_path))
        self.rom_analysis = analyzer.analyze()
        analyzer.print_summary()

        # Salva relatório
        analyzer.export_report(str(self.output_dir / 'rom_analysis.json'))

    def _run_compression_detection(self):
        """Etapa 2: Detecção de compressão."""
        # Carrega dados
        with open(self.rom_path, 'rb') as f:
            data = f.read()
            if len(data) % 1024 == 512:
                data = data[512:]

        # Usa mapa de entropia da etapa anterior
        entropy_map = self.rom_analysis.get('entropy_map', [])

        detector = CompressionDetector(data, entropy_map)
        self.compressed_regions = detector.detect()
        detector.print_summary()
        detector.export_report(str(self.output_dir / 'compression_report.json'))

    def _run_text_scanning(self):
        """Etapa 3: Varredura de texto."""
        # Carrega dados
        with open(self.rom_path, 'rb') as f:
            data = f.read()
            if len(data) % 1024 == 512:
                data = data[512:]

        # Usa regiões candidatas a texto da análise estrutural
        text_regions = self.rom_analysis.get('regions', {}).get('text_candidates', [])

        scanner = TextScanner(data, text_regions)
        self.text_candidates = scanner.scan(min_length=4, max_length=256)
        scanner.print_top_candidates(10)
        scanner.export_candidates(str(self.output_dir / 'text_candidates.json'), top_n=200)

    def _run_charset_inference(self):
        """Etapa 4: Inferência de tabelas de caracteres."""
        engine = CharsetInferenceEngine(self.text_candidates)
        self.charset_tables = engine.infer_charsets()
        engine.print_candidates(3)
        engine.export_tables(str(self.output_dir / 'inferred_charsets'))

    def _run_pointer_scanning(self):
        """Etapa 5: Detecção de ponteiros."""
        # Carrega dados
        with open(self.rom_path, 'rb') as f:
            data = f.read()
            if len(data) % 1024 == 512:
                data = data[512:]

        # Converte text_candidates para formato esperado pelo PointerScanner
        text_regions = [
            {
                'offset_dec': c.offset,
                'length': c.length
            }
            for c in self.text_candidates
        ]

        scanner = PointerScanner(data, text_regions)
        self.pointer_tables = scanner.scan(pointer_sizes=[2, 3], endianness_modes=['little'])
        scanner.print_summary(5)
        scanner.export_tables(str(self.output_dir / 'pointer_tables.json'))

    def _consolidate_results(self) -> Dict:
        """Consolida todos os resultados em estrutura unificada."""
        # Decodifica textos usando melhor charset
        best_charset = self.charset_tables[0] if self.charset_tables else None

        extracted_texts = []
        for i, candidate in enumerate(self.text_candidates[:100], 1):  # Top 100
            # Decodifica com charset inferido
            decoded_text = ""
            if best_charset:
                for byte in candidate.data:
                    char = best_charset.byte_to_char.get(byte, f'[{byte:02X}]')
                    decoded_text += char
            else:
                # Fallback: tenta ASCII
                try:
                    decoded_text = candidate.data.decode('ascii', errors='ignore')
                except:
                    decoded_text = candidate.data.hex()

            # Encontra ponteiros que apontam para este texto
            pointing_pointers = []
            for table in self.pointer_tables:
                for pointer in table.pointers:
                    if abs(pointer.target_offset - candidate.offset) < 16:  # Tolerância
                        pointing_pointers.append({
                            'pointer_offset': hex(pointer.offset),
                            'pointer_value': hex(pointer.value),
                            'confidence': round(pointer.confidence, 3)
                        })

            text_entry = {
                'id': i,
                'offset': hex(candidate.offset),
                'offset_dec': candidate.offset,
                'raw_bytes': candidate.data[:64].hex(),  # Primeiros 64 bytes
                'length': candidate.length,
                'score': round(candidate.score, 3),
                'encoding_hints': candidate.encoding_hints,
                'decoded_text': decoded_text,
                'pointers': pointing_pointers,
                'is_compressed': self._is_in_compressed_region(candidate.offset)
            }

            extracted_texts.append(text_entry)

        self.extracted_texts = extracted_texts

        # Estrutura consolidada
        return {
            'rom_info': {
                'filename': self.rom_path.name,
                'size': self.rom_analysis['file_info']['size_bytes'],
                'platform': self.rom_analysis['platform']['platform'],
                'md5': self.rom_analysis['file_info']['md5']
            },
            'analysis_summary': {
                'text_candidates_found': len(self.text_candidates),
                'charset_tables_generated': len(self.charset_tables),
                'pointer_tables_found': len(self.pointer_tables),
                'compressed_regions': len(self.compressed_regions),
                'best_charset': self.charset_tables[0].name if self.charset_tables else 'none'
            },
            'extracted_texts': extracted_texts,
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'pipeline_version': '1.0',
                'ready_for_translation': len(extracted_texts) > 0
            }
        }

    def _is_in_compressed_region(self, offset: int) -> bool:
        """Verifica se offset está em região comprimida."""
        for region in self.compressed_regions:
            if region.offset <= offset < region.offset + region.size:
                return True
        return False

    def _export_universal_format(self, data: Dict):
        """Exporta em formato universal JSON."""
        output_file = self.output_dir / 'extracted_texts_universal.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Universal format exported to: {output_file}")
        print(f"\n📊 EXTRACTION SUMMARY:")
        print(f"   Total texts extracted: {len(data['extracted_texts'])}")
        print(f"   Charset tables: {data['analysis_summary']['charset_tables_generated']}")
        print(f"   Pointer tables: {data['analysis_summary']['pointer_tables_found']}")
        print(f"   Best charset: {data['analysis_summary']['best_charset']}")
        print(f"\n📁 All outputs saved to: {self.output_dir}")


def extract_rom_universal(rom_path: str, output_dir: Optional[str] = None) -> Dict:
    """
    Função de conveniência para extração completa.

    Args:
        rom_path: Caminho da ROM
        output_dir: Diretório de saída (opcional)

    Returns:
        Dicionário com resultados consolidados
    """
    pipeline = UniversalExtractionPipeline(rom_path, output_dir)
    return pipeline.run_full_analysis()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python universal_pipeline.py <rom_file> [output_dir]")
        print("\nExample:")
        print("  python universal_pipeline.py game.smc")
        print("  python universal_pipeline.py game.smc ./extraction_output")
        sys.exit(1)

    rom_file = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None

    extract_rom_universal(rom_file, output)
