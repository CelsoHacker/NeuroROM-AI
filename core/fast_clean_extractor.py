# -*- coding: utf-8 -*-
"""
FAST CLEAN EXTRACTOR - Extrator Rápido com Filtro Inteligente
==============================================================

⚠️  DEPRECATED (V1) - Este módulo será removido em versões futuras.
    Use: orchestrator.plugin_orchestrator.run_extraction()

    Este extrator gera arquivos {rom_name}_CLEAN_REPORT.txt que vazam
    nomes de arquivo. A nova API usa CRC32 para naming neutro.

Versão ULTRA RÁPIDA focada em extrair APENAS texto inglês puro.

Estratégia:
1. Extrai apenas ASCII legível (0x20-0x7E)
2. Aplica super filtro para remover lixo
3. Processa ROM em 5-10 segundos

Autor: Sistema V5
Data: 2026-01
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict
from collections import Counter

# Importa super filtro
try:
    from .super_text_filter import SuperTextFilter
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from super_text_filter import SuperTextFilter


class FastCleanExtractor:
    """
    Extrator rápido focado em ASCII + Filtro inteligente + Suporte TBL.
    """

    def __init__(self, rom_path: str, tbl_path: str = None):
        self.rom_path = Path(rom_path)

        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(rom_path, 'rb') as f:
            self.rom_data = f.read()

        print(f"📏 Tamanho: {len(self.rom_data):,} bytes\n")

        self.text_filter = SuperTextFilter()
        self.min_length = 4

        # NOVO: Suporte a TBL
        try:
            from .tbl_loader import TBLLoader
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from tbl_loader import TBLLoader

        self.tbl_loader = TBLLoader()

        if tbl_path:
            self.tbl_loader.load_tbl(tbl_path)
            self.char_table = self.tbl_loader.char_map
        else:
            self.char_table = self.tbl_loader.auto_detect_table(self.rom_data)

    def extract_ascii_strings(self) -> List[Tuple[int, str]]:
        """
        Extrai strings ASCII puras (0x20-0x7E).
        MUITO MAIS RÁPIDO que método byte-por-byte.
        """
        print("📝 Extraindo strings ASCII...")

        strings_found = []

        # Regex para encontrar sequências de caracteres ASCII imprimíveis
        # Mínimo 4 caracteres consecutivos
        ascii_pattern = re.compile(b'[\x20-\x7E]{4,200}')

        for match in ascii_pattern.finditer(self.rom_data):
            offset = match.start()
            raw_bytes = match.group()

            try:
                text = raw_bytes.decode('ascii', errors='ignore')

                # Remove espaços extras
                text = text.strip()

                if len(text) >= self.min_length:
                    strings_found.append((offset, text))
            except:
                pass

        print(f"✅ {len(strings_found)} strings ASCII encontradas")

        return strings_found

    def extract_with_table(self) -> List[Tuple[int, str]]:
        """
        Extrai usando tabela customizada (técnica clássica de romhacking).

        Baseado em:
        - Livro Branco do Romhacking (Fserve)
        - Tutoriais PO.B.R.E
        """
        print("📝 Extraindo com tabela customizada...")

        strings_found = []
        offset = 0

        while offset < len(self.rom_data) - self.min_length:
            byte = self.rom_data[offset]

            # Verifica se byte está na tabela
            if byte in self.char_table:
                # Tenta extrair string
                text = []
                length = 0

                for i in range(200):  # Max 200 chars
                    if offset + i >= len(self.rom_data):
                        break

                    current_byte = self.rom_data[offset + i]

                    # Terminadores (00, FF)
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
                        # Byte desconhecido - para
                        break

                # Valida string extraída
                if len(text) >= self.min_length:
                    final_text = ''.join(text).strip()
                    if len(final_text) >= self.min_length:
                        strings_found.append((offset, final_text))
                        offset += length if length > 0 else 1
                        continue

            offset += 1

        print(f"✅ {len(strings_found)} strings com tabela encontradas")

        return strings_found

    def remove_duplicates(self, strings: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        """Remove strings duplicadas, mantendo primeira ocorrência."""
        print("\n🔧 Removendo duplicatas...")

        seen = {}
        unique = []

        for offset, text in strings:
            if text not in seen:
                seen[text] = offset
                unique.append((offset, text))

        print(f"✅ {len(unique)} strings únicas")

        return unique

    def apply_smart_filter(self, strings: List[Tuple[int, str]]) -> Tuple[List[Tuple[int, str]], Counter]:
        """Aplica super filtro para remover lixo."""
        print("\n🔥 Aplicando SUPER TEXT FILTER...")

        filtered = []
        rejection_stats = Counter()

        for offset, text in strings:
            is_valid, reason = self.text_filter.is_valid_text(text)

            if is_valid:
                filtered.append((offset, text))
            else:
                rejection_stats[reason] += 1

        approval_rate = (len(filtered) / len(strings) * 100) if strings else 0
        print(f"✅ {len(filtered)} strings válidas ({approval_rate:.1f}%)")
        print(f"❌ {len(strings) - len(filtered)} rejeitadas")

        return filtered, rejection_stats

    def save_results(self, strings: List[Tuple[int, str]], rejection_stats: Counter) -> Dict:
        """Salva arquivos de resultado."""
        print("\n💾 Salvando arquivos...")

        output_dir = self.rom_path.parent
        rom_name = self.rom_path.stem

        # Arquivo principal
        output_file = output_dir / f"{rom_name}_CLEAN_EXTRACTED.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# FAST CLEAN EXTRACTOR - Textos Limpos\n")
            f.write("# " + "="*76 + "\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Total de strings: {len(strings)}\n")
            f.write("# Filtro: SUPER TEXT FILTER (English words validation)\n")
            f.write("# " + "="*76 + "\n\n")

            for offset, text in strings:
                f.write(f"[0x{offset:x}] {text}\n")

        print(f"✅ {output_file.name}")

        # Relatório
        report_file = output_dir / f"{rom_name}_CLEAN_REPORT.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("FAST CLEAN EXTRACTOR - RELATÓRIO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Tamanho: {len(self.rom_data):,} bytes\n\n")

            f.write(f"Strings válidas: {len(strings)}\n\n")

            if rejection_stats:
                f.write("RAZÕES DE REJEIÇÃO:\n")
                for reason, count in rejection_stats.most_common():
                    f.write(f"  - {reason}: {count} strings\n")
                f.write("\n")

            f.write("="*80 + "\n")
            f.write("TODAS AS STRINGS EXTRAÍDAS:\n")
            f.write("="*80 + "\n\n")

            for idx, (offset, text) in enumerate(strings, 1):
                f.write(f"{idx:3d}. [0x{offset:05x}] {text}\n")

        print(f"✅ {report_file.name}")

        return {
            'output_file': str(output_file),
            'report_file': str(report_file)
        }

    def extract_all(self) -> Dict:
        """Execução completa com DUPLA EXTRAÇÃO (ASCII + TBL)."""
        print("="*80)
        print("🚀 FAST CLEAN EXTRACTOR + TBL SUPPORT")
        print("="*80 + "\n")

        # ETAPA 1: Extrai ASCII
        ascii_strings = self.extract_ascii_strings()

        # ETAPA 2: Extrai com tabela customizada
        table_strings = self.extract_with_table()

        # ETAPA 3: Combina resultados (remove duplicatas entre os 2 métodos)
        print("\n🔧 Combinando resultados...")
        all_strings = ascii_strings + table_strings

        # ETAPA 4: Remove duplicatas
        unique_strings = self.remove_duplicates(all_strings)

        # ETAPA 5: Aplica filtro
        filtered_strings, rejection_stats = self.apply_smart_filter(unique_strings)

        # ETAPA 6: Salva
        files = self.save_results(filtered_strings, rejection_stats)

        # Resumo
        print("\n" + "="*80)
        print("✅ EXTRAÇÃO CONCLUÍDA!")
        print("="*80)
        print(f"\n📊 RESUMO:")
        print(f"   📝 ASCII encontradas: {len(ascii_strings)}")
        print(f"   📋 Tabela encontradas: {len(table_strings)}")
        print(f"   🔄 Total único: {len(unique_strings)}")
        print(f"   ✅ Strings válidas: {len(filtered_strings)}")

        if unique_strings:
            approval = (len(filtered_strings) / len(unique_strings) * 100)
            print(f"   📈 Taxa de aprovação: {approval:.1f}%")

        print(f"\n📂 ARQUIVOS GERADOS:")
        print(f"   - {Path(files['output_file']).name}")
        print(f"   - {Path(files['report_file']).name}")
        print("\n" + "="*80 + "\n")

        return {
            'rom_path': str(self.rom_path),
            'rom_size': len(self.rom_data),
            'ascii_strings': len(ascii_strings),
            'table_strings': len(table_strings),
            'unique_strings': len(unique_strings),
            'valid_strings': len(filtered_strings),
            'approval_rate': (len(filtered_strings) / len(unique_strings) * 100) if unique_strings else 0,
            **files
        }


def extract_rom_fast(rom_path: str) -> Dict:
    """Função principal."""
    extractor = FastCleanExtractor(rom_path)
    return extractor.extract_all()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        extract_rom_fast(rom_path)
    else:
        print("Uso: python fast_clean_extractor.py <rom_path>")
        print("\nExemplo:")
        print('  python fast_clean_extractor.py "Super Mario World.smc"')
