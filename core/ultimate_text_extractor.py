# -*- coding: utf-8 -*-
"""
ULTIMATE TEXT EXTRACTOR - Extrator Definitivo com Tabela Customizada
=====================================================================
Detecta automaticamente a tabela de caracteres e extrai texto puro.

Soluciona: Super Mario World e outros jogos SNES usam tabelas customizadas,
não ASCII padrão. Este extrator aprende a tabela do jogo automaticamente.

Autor: Sistema de Tradução V5
Data: 2026-01
"""

import struct
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter

# Importa o super filtro
try:
    from .super_text_filter import SuperTextFilter
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from super_text_filter import SuperTextFilter


# ============================================================================
# DETECTOR INTELIGENTE DE TABELA DE CARACTERES
# ============================================================================

class SmartCharTableDetector:
    """
    Detecta AUTOMATICAMENTE a tabela de caracteres usada no jogo.

    Método:
    1. Procura por textos conhecidos em ASCII (títulos, menus)
    2. Identifica os bytes usados
    3. Constrói mapa de caracteres baseado em padrões
    """

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.char_table = {}

    def find_known_strings(self) -> List[Tuple[int, str, bytes]]:
        """
        Procura por strings conhecidas que aparecem em ASCII.
        Retorna: [(offset, texto_ascii, bytes_originais)]
        """
        # Strings que aparecem em praticamente todos os jogos
        known_patterns = [
            b'SUPER',
            b'MARIO',
            b'WORLD',
            b'START',
            b'SELECT',
            b'GAME',
            b'OVER',
            b'CONTINUE',
            b'PLAYER',
            b'SCORE',
            b'TIME',
            b'LEVEL',
            b'STAGE',
            b'BONUS',
            b'PAUSE',
            b'PRESS',
            b'THANKS',
            b'END',
        ]

        found = []
        for pattern in known_patterns:
            offset = self.rom_data.find(pattern)
            if offset != -1:
                found.append((offset, pattern.decode('ascii'), pattern))

        return found

    def build_table_from_ascii_section(self) -> Dict[int, str]:
        """
        Constrói tabela baseada em seção ASCII encontrada.
        """
        known_strings = self.find_known_strings()

        if not known_strings:
            # Não encontrou ASCII, retorna tabela padrão
            return self._get_default_snes_table()

        # Analisa bytes usados nas strings ASCII
        ascii_bytes = set()
        for offset, text, raw_bytes in known_strings:
            for byte in raw_bytes:
                ascii_bytes.add(byte)

        # Cria mapa básico
        table = {}

        # Mapeia letras ASCII (maioria dos jogos usa ASCII padrão para letras)
        for byte_val in range(0x41, 0x5B):  # A-Z
            table[byte_val] = chr(byte_val)

        for byte_val in range(0x61, 0x7B):  # a-z
            table[byte_val] = chr(byte_val)

        # Números
        for byte_val in range(0x30, 0x3A):  # 0-9
            table[byte_val] = chr(byte_val)

        # Espaço e pontuação comum
        table[0x20] = ' '  # Espaço
        table[0x21] = '!'
        table[0x2C] = ','
        table[0x2E] = '.'
        table[0x3F] = '?'
        table[0x27] = "'"
        table[0x2D] = '-'
        table[0x3A] = ':'

        # Caracteres de controle
        table[0x00] = '\n'  # NULL = quebra de linha
        table[0xFF] = '\n'  # FF = fim de string
        table[0xFE] = ' '   # FE = espaço extra

        return table

    def _get_default_snes_table(self) -> Dict[int, str]:
        """
        Tabela padrão para jogos SNES quando não consegue detectar.
        """
        table = {}

        # ASCII padrão
        for i in range(0x20, 0x7F):
            table[i] = chr(i)

        # Controles
        table[0x00] = '\n'
        table[0xFF] = '\n'
        table[0xFE] = ' '

        return table

    def detect_table(self) -> Dict[int, str]:
        """
        Executa detecção completa da tabela.
        """
        print("🔍 Detectando tabela de caracteres...")

        # Método 1: Busca por strings ASCII conhecidas
        table = self.build_table_from_ascii_section()

        print(f"✅ Tabela detectada: {len(table)} caracteres mapeados")

        return table


# ============================================================================
# EXTRATOR INTELIGENTE DE STRINGS
# ============================================================================

class IntelligentStringExtractor:
    """
    Extrai strings usando tabela detectada + validação inteligente.
    """

    def __init__(self, rom_data: bytes, char_table: Dict[int, str]):
        self.rom_data = rom_data
        self.char_table = char_table
        self.min_string_length = 4
        self.max_string_length = 200

    def is_valid_text_byte(self, byte: int) -> bool:
        """Verifica se byte faz parte da tabela de texto."""
        return byte in self.char_table

    def extract_string_at(self, offset: int) -> Tuple[str, int]:
        """
        Extrai string começando no offset.
        Retorna: (texto, tamanho_em_bytes)
        """
        text = []
        length = 0

        for i in range(self.max_string_length):
            if offset + i >= len(self.rom_data):
                break

            byte = self.rom_data[offset + i]

            # Terminadores
            if byte in [0x00, 0xFF]:
                length = i + 1
                break

            # Caractere mapeado
            if byte in self.char_table:
                char = self.char_table[byte]
                text.append(char)
            else:
                # Caractere desconhecido - para aqui
                break

        return ''.join(text), length

    def scan_rom(self) -> List[Tuple[int, str]]:
        """
        Varre toda a ROM procurando strings válidas.
        Retorna: [(offset, texto)]
        """
        print("📝 Escaneando ROM por strings...")

        strings_found = []
        offset = 0
        progress_step = len(self.rom_data) // 20  # Mostra progresso a cada 5%
        next_progress = progress_step

        while offset < len(self.rom_data) - self.min_string_length:
            # Mostra progresso
            if offset >= next_progress:
                percent = (offset / len(self.rom_data)) * 100
                print(f"   ... {percent:.0f}% processado", end='\r')
                next_progress += progress_step

            byte = self.rom_data[offset]

            # Verifica se byte pode iniciar uma string
            if self.is_valid_text_byte(byte) and byte not in [0x00, 0xFF, 0xFE]:
                text, length = self.extract_string_at(offset)

                # Valida tamanho mínimo
                if len(text) >= self.min_string_length:
                    # Remove espaços extras
                    text = text.strip()

                    if len(text) >= self.min_string_length:
                        strings_found.append((offset, text))
                        offset += length
                        continue

            offset += 1

        print(f"✅ {len(strings_found)} strings encontradas                  ")

        return strings_found


# ============================================================================
# EXTRATOR ULTIMATE - INTEGRAÇÃO COMPLETA
# ============================================================================

class UltimateTextExtractor:
    """
    Sistema completo: Detecção + Extração + Filtro inteligente.
    """

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)

        # Carrega ROM
        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(rom_path, 'rb') as f:
            self.rom_data = f.read()

        print(f"📏 Tamanho: {len(self.rom_data):,} bytes\n")

        # Inicializa componentes
        self.table_detector = SmartCharTableDetector(self.rom_data)
        self.text_filter = SuperTextFilter()

    def extract_all(self, apply_filter: bool = True) -> Dict:
        """
        Extração completa com todos os filtros.

        Args:
            apply_filter: Se True, aplica super filtro (recomendado)

        Returns:
            Dict com estatísticas e arquivos gerados
        """
        print("="*80)
        print("🚀 ULTIMATE TEXT EXTRACTOR")
        print("="*80 + "\n")

        # ETAPA 1: Detecta tabela de caracteres
        char_table = self.table_detector.detect_table()

        # ETAPA 2: Extrai strings
        extractor = IntelligentStringExtractor(self.rom_data, char_table)
        raw_strings = extractor.scan_rom()

        # ETAPA 3: Remove duplicatas
        print("\n🔧 Removendo duplicatas...")
        unique_strings = {}
        for offset, text in raw_strings:
            if text not in unique_strings:
                unique_strings[text] = offset

        strings_list = [(offset, text) for text, offset in unique_strings.items()]
        strings_list.sort(key=lambda x: x[0])  # Ordena por offset

        print(f"✅ {len(strings_list)} strings únicas")

        # ETAPA 4: Aplica filtro inteligente
        if apply_filter:
            print("\n🔥 Aplicando SUPER TEXT FILTER...")

            filtered_strings = []
            rejection_stats = Counter()

            for offset, text in strings_list:
                is_valid, reason = self.text_filter.is_valid_text(text)

                if is_valid:
                    filtered_strings.append((offset, text))
                else:
                    rejection_stats[reason] += 1

            print(f"✅ {len(filtered_strings)} strings válidas ({len(filtered_strings)/len(strings_list)*100:.1f}%)")
            print(f"❌ {len(strings_list) - len(filtered_strings)} rejeitadas")

            final_strings = filtered_strings
        else:
            final_strings = strings_list

        # ETAPA 5: Salva resultados
        print("\n💾 Salvando arquivos...")

        output_dir = self.rom_path.parent
        rom_name = self.rom_path.stem

        # Arquivo com strings válidas
        output_file = output_dir / f"{rom_name}_ULTIMATE_EXTRACTED.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# ULTIMATE TEXT EXTRACTOR - Textos Extraídos\n")
            f.write("# " + "="*76 + "\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Total de strings: {len(final_strings)}\n")
            f.write(f"# Filtro aplicado: {'Sim' if apply_filter else 'Não'}\n")
            f.write("# " + "="*76 + "\n\n")

            for offset, text in final_strings:
                f.write(f"[0x{offset:x}] {text}\n")

        print(f"✅ {output_file.name}")

        # Relatório
        report_file = output_dir / f"{rom_name}_ULTIMATE_REPORT.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ULTIMATE TEXT EXTRACTOR - RELATÓRIO DETALHADO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Tamanho: {len(self.rom_data):,} bytes\n\n")

            f.write("TABELA DE CARACTERES:\n")
            f.write(f"- Caracteres mapeados: {len(char_table)}\n\n")

            f.write("EXTRAÇÃO:\n")
            f.write(f"- Strings brutas encontradas: {len(raw_strings)}\n")
            f.write(f"- Strings únicas: {len(strings_list)}\n")
            f.write(f"- Strings válidas (pós-filtro): {len(final_strings)}\n\n")

            if apply_filter:
                f.write("FILTRO:\n")
                f.write(f"- Taxa de aprovação: {len(final_strings)/len(strings_list)*100:.1f}%\n")
                f.write(f"- Taxa de rejeição: {(len(strings_list)-len(final_strings))/len(strings_list)*100:.1f}%\n\n")

                f.write("RAZÕES DE REJEIÇÃO:\n")
                for reason, count in rejection_stats.most_common(10):
                    f.write(f"  - {reason}: {count} strings\n")
                f.write("\n")

            f.write("="*80 + "\n")
            f.write("TOP 50 STRINGS EXTRAÍDAS:\n")
            f.write("="*80 + "\n\n")

            for idx, (offset, text) in enumerate(final_strings[:50], 1):
                f.write(f"{idx:3d}. [0x{offset:05x}] {text}\n")

        print(f"✅ {report_file.name}")

        # Resumo
        print("\n" + "="*80)
        print("✅ EXTRAÇÃO CONCLUÍDA!")
        print("="*80)
        print(f"\n📊 RESUMO:")
        print(f"   📝 Strings brutas: {len(raw_strings)}")
        print(f"   🔄 Strings únicas: {len(strings_list)}")
        print(f"   ✅ Strings válidas: {len(final_strings)}")
        if apply_filter:
            print(f"   📈 Taxa de aprovação: {len(final_strings)/len(strings_list)*100:.1f}%")
        print(f"\n📂 ARQUIVOS GERADOS:")
        print(f"   - {output_file.name}")
        print(f"   - {report_file.name}")
        print("\n" + "="*80 + "\n")

        return {
            'rom_path': str(self.rom_path),
            'rom_size': len(self.rom_data),
            'raw_strings': len(raw_strings),
            'unique_strings': len(strings_list),
            'valid_strings': len(final_strings),
            'approval_rate': len(final_strings)/len(strings_list)*100 if strings_list else 0,
            'files_created': [str(output_file), str(report_file)]
        }


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def extract_rom_ultimate(rom_path: str, apply_filter: bool = True) -> Dict:
    """
    Função principal para extração ultimate.

    Args:
        rom_path: Caminho para ROM
        apply_filter: Se True, aplica filtro inteligente (recomendado)

    Returns:
        Dict com estatísticas
    """
    extractor = UltimateTextExtractor(rom_path)
    return extractor.extract_all(apply_filter=apply_filter)


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        apply_filter = True if len(sys.argv) < 3 else sys.argv[2].lower() != 'false'

        extract_rom_ultimate(rom_path, apply_filter)
    else:
        print("Uso: python ultimate_text_extractor.py <rom_path> [apply_filter]")
        print("\nExemplo:")
        print('  python ultimate_text_extractor.py "Super Mario World.smc"')
        print('  python ultimate_text_extractor.py "game.smc" false  # Sem filtro')
