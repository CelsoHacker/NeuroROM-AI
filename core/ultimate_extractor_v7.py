# -*- coding: utf-8 -*-
"""
ULTIMATE EXTRACTOR V7.0 - ULTIMATE EXTRACTION SUITE
====================================================
Sistema de extração de texto definitivo com 3 motores em cascata:

1. EXTRAÇÃO PRINCIPAL (ASCII + TBL) - V6.0
2. RELATIVE PATTERN ENGINE (Quebrador de Tabela) - V7.0 NOVO
3. DEEP SCAVENGER ENGINE (Varredura de Lacunas) - V7.0 NOVO

Pipeline:
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 1: Extração Principal (ASCII + TBL auto-detect)      │
│   └─> Se < 100 válidas E Entropia < 3.8                    │
│       └─> ATIVA Pattern Engine (quebra tabela matemático)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 2: Relative Pattern Engine                           │
│   └─> Detecta tabela usando vetores matemáticos            │
│   └─> Gera arquivo .tbl automaticamente                    │
│   └─> Re-executa extração com tabela detectada             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 3: Deep Scavenger Engine (SEMPRE executa)            │
│   └─> Analisa gaps entre strings                           │
│   └─> Extrai com filtros relaxados                         │
│   └─> Marca strings como [RECOVERED]                       │
└─────────────────────────────────────────────────────────────┘

Mantém toda lógica V6.0:
- Super Text Filter (validação de palavras inglesas)
- TBL Loader (suporte a tabelas customizadas)
- Estatísticas detalhadas

Autor: Sistema V7.0 ULTIMATE
Data: 2026-01
"""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import Counter

# Importa componentes V6.0
try:
    from .super_text_filter import SuperTextFilter
    from .tbl_loader import TBLLoader
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from super_text_filter import SuperTextFilter
    from tbl_loader import TBLLoader

# Importa novos motores V7.0
try:
    from .relative_pattern_engine import RelativePatternEngine
    from .deep_scavenger_engine import DeepScavengerEngine
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from relative_pattern_engine import RelativePatternEngine
    from deep_scavenger_engine import DeepScavengerEngine


class UltimateExtractorV7:
    """
    Extrator definitivo V7.0 com 3 motores em cascata.
    """

    def __init__(self, rom_path: str, tbl_path: Optional[str] = None):
        self.rom_path = Path(rom_path)

        print("="*80)
        print("🚀 ULTIMATE EXTRACTION SUITE V7.0")
        print("="*80)
        print(f"📂 ROM: {self.rom_path.name}")

        # Carrega ROM
        with open(rom_path, 'rb') as f:
            self.rom_data = f.read()

        print(f"📏 Tamanho: {len(self.rom_data):,} bytes")
        print("="*80 + "\n")

        # Componentes V6.0
        self.text_filter = SuperTextFilter()
        self.tbl_loader = TBLLoader()

        # Tabela inicial
        if tbl_path:
            print(f"📋 Carregando tabela customizada: {Path(tbl_path).name}")
            self.tbl_loader.load_tbl(tbl_path)
            self.char_table = self.tbl_loader.char_map
            self.using_custom_tbl = True
        else:
            print("🔍 Auto-detectando tipo de tabela...")
            self.char_table = self.tbl_loader.auto_detect_table(self.rom_data)
            self.using_custom_tbl = False

        # Novos motores V7.0
        self.pattern_engine = RelativePatternEngine(self.rom_data)
        self.scavenger_engine = None  # Inicializado depois

        # Configurações
        self.min_length = 4

    def extract_ascii_strings(self) -> List[Tuple[int, str]]:
        """
        Extrai strings ASCII puras (V6.0).
        """
        import re

        print("📝 [MOTOR 1A] Extraindo strings ASCII...")

        strings_found = []
        ascii_pattern = re.compile(b'[\x20-\x7E]{4,200}')

        for match in ascii_pattern.finditer(self.rom_data):
            offset = match.start()
            raw_bytes = match.group()

            try:
                text = raw_bytes.decode('ascii', errors='ignore').strip()

                if len(text) >= self.min_length:
                    strings_found.append((offset, text))
            except:
                pass

        print(f"   ✅ {len(strings_found)} strings ASCII encontradas")
        return strings_found

    def extract_with_table(self) -> List[Tuple[int, str]]:
        """
        Extrai usando tabela de caracteres (V6.0).
        """
        print("📝 [MOTOR 1B] Extraindo com tabela customizada...")

        strings_found = []
        offset = 0

        while offset < len(self.rom_data) - self.min_length:
            byte = self.rom_data[offset]

            if byte in self.char_table:
                text = []
                length = 0

                for i in range(200):
                    if offset + i >= len(self.rom_data):
                        break

                    current_byte = self.rom_data[offset + i]

                    # Terminadores
                    if current_byte in [0x00, 0xFF]:
                        if len(text) >= self.min_length:
                            length = i + 1
                            break
                        else:
                            break

                    # Mapeia byte
                    if current_byte in self.char_table:
                        text.append(self.char_table[current_byte])
                    else:
                        break

                # Valida string
                if len(text) >= self.min_length:
                    final_text = ''.join(text).strip()
                    if len(final_text) >= self.min_length:
                        strings_found.append((offset, final_text))
                        offset += length if length > 0 else 1
                        continue

            offset += 1

        print(f"   ✅ {len(strings_found)} strings com tabela encontradas")
        return strings_found

    def remove_duplicates(self, strings: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        """Remove duplicatas mantendo primeira ocorrência (V6.0)."""
        print("\n🔧 Removendo duplicatas...")

        seen = {}
        unique = []

        for offset, text in strings:
            if text not in seen:
                seen[text] = offset
                unique.append((offset, text))

        print(f"   ✅ {len(unique)} strings únicas")
        return unique

    def apply_filter(self, strings: List[Tuple[int, str]]) -> Tuple[List[Tuple[int, str]], Counter]:
        """Aplica Super Text Filter (V6.0)."""
        print("\n🔥 Aplicando SUPER TEXT FILTER (V6.0)...")

        filtered = []
        rejection_stats = Counter()

        for offset, text in strings:
            is_valid, reason = self.text_filter.is_valid_text(text)

            if is_valid:
                filtered.append((offset, text))
            else:
                rejection_stats[reason] += 1

        if strings:
            approval_rate = (len(filtered) / len(strings) * 100)
            print(f"   ✅ {len(filtered)} strings válidas ({approval_rate:.1f}%)")
            print(f"   ❌ {len(strings) - len(filtered)} rejeitadas")
        else:
            print(f"   ✅ 0 strings para filtrar")

        return filtered, rejection_stats

    def run_pattern_engine(self, ascii_valid_count: int) -> bool:
        """
        Executa Pattern Engine se necessário (V7.0 NOVO).

        Returns:
            True se detectou nova tabela e deve re-extrair
        """
        # Verifica critérios de ativação
        if not self.pattern_engine.should_activate(ascii_valid_count):
            return False

        # Detecta tabela
        detected_table = self.pattern_engine.detect_table()

        if detected_table:
            # Salva .tbl
            output_tbl = self.rom_path.parent / f"{self.rom_path.stem}_DETECTED.tbl"
            self.pattern_engine.save_detected_table(str(output_tbl))

            # Atualiza tabela
            self.char_table = detected_table

            print(f"\n🎉 TABELA DETECTADA COM SUCESSO!")
            print(f"   📋 {len(detected_table)} caracteres mapeados")
            print(f"   💾 Salva em: {output_tbl.name}")
            print(f"\n🔄 Re-executando extração com tabela detectada...\n")

            return True

        return False

    def run_scavenger_engine(self, extracted_offsets: List[int]) -> Tuple[List[Tuple[int, str]], Dict]:
        """
        Executa Deep Scavenger Engine (V7.0 NOVO).

        Returns:
            (recovered_strings, statistics)
        """
        self.scavenger_engine = DeepScavengerEngine(self.rom_data, self.char_table)
        return self.scavenger_engine.scavenge(extracted_offsets)

    def save_results(self, main_strings: List[Tuple[int, str]],
                    recovered_strings: List[Tuple[int, str]],
                    rejection_stats: Counter,
                    stats: Dict) -> Dict:
        """Salva arquivos de resultado (V6.0 + V7.0)."""
        print("\n💾 Salvando arquivos...")

        output_dir = self.rom_path.parent
        rom_name = self.rom_path.stem

        # Arquivo principal
        output_file = output_dir / f"{rom_name}_V7_EXTRACTED.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# ULTIMATE EXTRACTION SUITE V7.0\n")
            f.write("# " + "="*76 + "\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Strings principais: {len(main_strings)}\n")
            f.write(f"# Strings recuperadas: {len(recovered_strings)}\n")
            f.write(f"# Total: {len(main_strings) + len(recovered_strings)}\n")
            f.write("# " + "="*76 + "\n\n")

            # Strings principais
            f.write("# STRINGS PRINCIPAIS (ASCII + TBL)\n")
            f.write("# " + "-"*76 + "\n\n")
            for offset, text in main_strings:
                f.write(f"[0x{offset:X}] {text}\n")

            # Strings recuperadas
            if recovered_strings:
                f.write("\n\n# STRINGS RECUPERADAS (Deep Scavenger Engine)\n")
                f.write("# " + "-"*76 + "\n\n")
                for offset, text in recovered_strings:
                    f.write(f"[0x{offset:X}] [RECOVERED] {text}\n")

        print(f"   ✅ {output_file.name}")

        # Relatório detalhado
        report_file = output_dir / f"{rom_name}_V7_REPORT.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ULTIMATE EXTRACTION SUITE V7.0 - RELATÓRIO COMPLETO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Tamanho: {len(self.rom_data):,} bytes\n\n")

            f.write("CONFIGURAÇÃO:\n")
            f.write(f"- Tabela customizada: {'Sim' if self.using_custom_tbl else 'Não (auto-detect)'}\n")
            f.write(f"- Pattern Engine ativado: {'Sim' if stats.get('pattern_engine_used') else 'Não'}\n")
            f.write(f"- Scavenger Engine usado: Sim (sempre)\n\n")

            f.write("RESULTADOS:\n")
            f.write(f"- ASCII encontradas: {stats['ascii_strings']}\n")
            f.write(f"- Tabela encontradas: {stats['table_strings']}\n")
            f.write(f"- Total único: {stats['unique_strings']}\n")
            f.write(f"- Strings válidas (pós-filtro): {stats['valid_strings']}\n")
            f.write(f"- Taxa de aprovação: {stats['approval_rate']:.1f}%\n\n")

            if recovered_strings:
                f.write("DEEP SCAVENGER:\n")
                f.write(f"- Lacunas analisadas: {stats['scavenger_total_gaps']}\n")
                f.write(f"- Áreas de interesse: {stats['scavenger_candidates']}\n")
                f.write(f"- Strings recuperadas: {stats['scavenger_recovered']}\n\n")

            if rejection_stats:
                f.write("RAZÕES DE REJEIÇÃO (Super Filter):\n")
                for reason, count in rejection_stats.most_common(10):
                    f.write(f"  - {reason}: {count} strings\n")
                f.write("\n")

            f.write("="*80 + "\n")
            f.write("TODAS AS STRINGS EXTRAÍDAS:\n")
            f.write("="*80 + "\n\n")

            f.write("PRINCIPAIS:\n")
            for idx, (offset, text) in enumerate(main_strings, 1):
                f.write(f"{idx:3d}. [0x{offset:05X}] {text}\n")

            if recovered_strings:
                f.write(f"\nRECUPERADAS:\n")
                for idx, (offset, text) in enumerate(recovered_strings, 1):
                    f.write(f"{idx:3d}. [0x{offset:05X}] [RECOVERED] {text}\n")

        print(f"   ✅ {report_file.name}")

        return {
            'output_file': str(output_file),
            'report_file': str(report_file)
        }

    def extract_all(self) -> Dict:
        """
        Pipeline completo V7.0 com 3 motores em cascata.
        """
        print("\n" + "="*80)
        print("🎯 INICIANDO PIPELINE V7.0")
        print("="*80 + "\n")

        # ====================================================================
        # ETAPA 1: EXTRAÇÃO PRINCIPAL (ASCII + TBL)
        # ====================================================================
        print("🔹 ETAPA 1: EXTRAÇÃO PRINCIPAL\n")

        ascii_strings = self.extract_ascii_strings()
        table_strings = self.extract_with_table()

        # Combina
        print("\n🔧 Combinando resultados...")
        all_strings = ascii_strings + table_strings
        unique_strings = self.remove_duplicates(all_strings)

        # Aplica filtro
        filtered_strings, rejection_stats = self.apply_filter(unique_strings)

        # ====================================================================
        # ETAPA 2: RELATIVE PATTERN ENGINE (SE NECESSÁRIO)
        # ====================================================================
        print("\n🔹 ETAPA 2: RELATIVE PATTERN ENGINE\n")

        pattern_engine_used = False
        if not self.using_custom_tbl:  # Só tenta detectar se não tiver .tbl customizado
            if self.run_pattern_engine(len(filtered_strings)):
                pattern_engine_used = True

                # Re-extrai com nova tabela
                print("📝 Re-extraindo com tabela detectada...")
                table_strings = self.extract_with_table()

                # Re-processa
                all_strings = ascii_strings + table_strings
                unique_strings = self.remove_duplicates(all_strings)
                filtered_strings, rejection_stats = self.apply_filter(unique_strings)

        # ====================================================================
        # ETAPA 3: DEEP SCAVENGER ENGINE (SEMPRE)
        # ====================================================================
        print("\n🔹 ETAPA 3: DEEP SCAVENGER ENGINE\n")

        # Coleta offsets extraídos
        extracted_offsets = [offset for offset, _ in filtered_strings]

        # Executa scavenger
        recovered_strings, scavenger_stats = self.run_scavenger_engine(extracted_offsets)

        # Filtra strings recuperadas
        if recovered_strings:
            print(f"\n🔥 Aplicando filtro nas strings recuperadas...")
            recovered_filtered = []
            for offset, text in recovered_strings:
                is_valid, _ = self.text_filter.is_valid_text(text)
                if is_valid:
                    recovered_filtered.append((offset, text))

            print(f"   ✅ {len(recovered_filtered)} strings recuperadas válidas")
            recovered_strings = recovered_filtered

        # ====================================================================
        # FINALIZAÇÃO
        # ====================================================================
        print("\n" + "="*80)
        print("💾 SALVANDO RESULTADOS")
        print("="*80 + "\n")

        stats = {
            'rom_path': str(self.rom_path),
            'rom_size': len(self.rom_data),
            'ascii_strings': len(ascii_strings),
            'table_strings': len(table_strings),
            'unique_strings': len(unique_strings),
            'valid_strings': len(filtered_strings),
            'approval_rate': (len(filtered_strings) / len(unique_strings) * 100) if unique_strings else 0,
            'pattern_engine_used': pattern_engine_used,
            'scavenger_total_gaps': scavenger_stats['total_gaps'],
            'scavenger_candidates': scavenger_stats['text_candidate_gaps'],
            'scavenger_recovered': len(recovered_strings),
        }

        files = self.save_results(filtered_strings, recovered_strings, rejection_stats, stats)

        # Resumo final
        print("\n" + "="*80)
        print("✅ EXTRAÇÃO V7.0 CONCLUÍDA!")
        print("="*80)
        print(f"\n📊 RESUMO FINAL:")
        print(f"   🔹 MOTOR 1 (ASCII + TBL):")
        print(f"      📝 ASCII: {len(ascii_strings)}")
        print(f"      📋 Tabela: {len(table_strings)}")
        print(f"      ✅ Válidas: {len(filtered_strings)}")

        if pattern_engine_used:
            print(f"   🔹 MOTOR 2 (Pattern Engine): ATIVADO")
            print(f"      ✅ Tabela detectada automaticamente")

        print(f"   🔹 MOTOR 3 (Deep Scavenger):")
        print(f"      📊 Lacunas: {stats['scavenger_total_gaps']}")
        print(f"      🎯 Áreas de interesse: {stats['scavenger_candidates']}")
        print(f"      ✅ Recuperadas: {len(recovered_strings)}")

        total_strings = len(filtered_strings) + len(recovered_strings)
        print(f"\n   🎉 TOTAL EXTRAÍDO: {total_strings} strings")

        print(f"\n📂 ARQUIVOS GERADOS:")
        print(f"   - {Path(files['output_file']).name}")
        print(f"   - {Path(files['report_file']).name}")

        if pattern_engine_used:
            print(f"   - {self.rom_path.stem}_DETECTED.tbl")

        print("\n" + "="*80 + "\n")

        return {
            **stats,
            'recovered_strings': len(recovered_strings),
            'total_strings': total_strings,
            **files
        }


def extract_rom_v7(rom_path: str, tbl_path: Optional[str] = None) -> Dict:
    """
    Função principal V7.0.

    Args:
        rom_path: Caminho da ROM
        tbl_path: Caminho da tabela customizada (opcional)

    Returns:
        Dict com estatísticas completas
    """
    extractor = UltimateExtractorV7(rom_path, tbl_path)
    return extractor.extract_all()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        tbl_path = sys.argv[2] if len(sys.argv) > 2 else None

        extract_rom_v7(rom_path, tbl_path)
    else:
        print("Uso: python ultimate_extractor_v7.py <rom_path> [tbl_path]")
        print("\nExemplo:")
        print('  python ultimate_extractor_v7.py "game.smc"')
        print('  python ultimate_extractor_v7.py "game.smc" "game.tbl"')
