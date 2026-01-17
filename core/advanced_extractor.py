# -*- coding: utf-8 -*-
"""
Advanced ROM Extractor - Sistema de Extração Inteligente
Versão 2.0 - Com Separação de Tiles, Auto-detecção TBL, e Filtros Avançados

Funcionalidades:
1. Detector de Tiles Gráficos (2BPP/4BPP bitplanes)
2. Auto-detecção de Tabela de Caracteres (ASCII vs TBL)
3. Filtro de Entropia Silábica (estrutura humana)
4. Detector de Ponteiros (padrões repetitivos)
5. Normalizador de Delimitadores (bytes nulos → hífens)
"""

import os
import sys
import struct
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter
import math


# ============================================================================
# 1. DETECTOR DE TILES GRÁFICOS
# ============================================================================

class TileDetector:
    """
    Identifica blocos de dados gráficos (Tiles) através de padrões de bitplanes.
    SNES usa 2BPP (4 cores) ou 4BPP (16 cores).
    """

    def __init__(self):
        self.tile_size_2bpp = 16  # 8x8 pixels, 2 bits/pixel = 16 bytes
        self.tile_size_4bpp = 32  # 8x8 pixels, 4 bits/pixel = 32 bytes

    def calculate_visual_entropy(self, data: bytes) -> float:
        """
        Calcula entropia visual dos dados.
        Tiles gráficos têm entropia específica (padrões de bitplanes).
        """
        if len(data) < 8:
            return 0.0

        # Conta transições de bits (tiles têm muitas transições)
        transitions = 0
        for i in range(len(data) - 1):
            xor = data[i] ^ data[i + 1]
            transitions += bin(xor).count('1')

        # Normaliza pela quantidade de bytes
        return transitions / len(data)

    def is_bitplane_pattern(self, data: bytes, bpp: int = 2) -> bool:
        """
        Verifica se os dados seguem padrão de bitplane.

        Bitplanes SNES:
        - 2BPP: 2 bytes para cada linha (8 pixels)
        - 4BPP: 4 bytes para cada linha (8 pixels)
        """
        if bpp == 2:
            tile_size = self.tile_size_2bpp
        elif bpp == 4:
            tile_size = self.tile_size_4bpp
        else:
            return False

        if len(data) < tile_size:
            return False

        # Calcula entropia visual
        entropy = self.calculate_visual_entropy(data[:tile_size])

        # Tiles típicos têm entropia entre 2.0 e 6.0
        # Texto puro tem entropia < 2.0
        # Dados aleatórios têm entropia > 6.0
        return 2.0 <= entropy <= 6.0

    def detect_tile_blocks(self, rom_data: bytes, min_tiles: int = 4) -> List[Tuple[int, int, str]]:
        """
        Detecta blocos contínuos de tiles gráficos na ROM.

        Returns:
            Lista de (offset_inicial, tamanho, tipo) onde tipo = '2BPP' ou '4BPP'
        """
        tile_blocks = []
        i = 0

        while i < len(rom_data) - self.tile_size_4bpp:
            # Testa 4BPP primeiro (maior bloco)
            if self.is_bitplane_pattern(rom_data[i:i+self.tile_size_4bpp], bpp=4):
                # Encontrou início de bloco 4BPP
                start = i
                tile_count = 0

                # Conta quantos tiles consecutivos existem
                while i < len(rom_data) - self.tile_size_4bpp:
                    if self.is_bitplane_pattern(rom_data[i:i+self.tile_size_4bpp], bpp=4):
                        tile_count += 1
                        i += self.tile_size_4bpp
                    else:
                        break

                # Só registra se tiver pelo menos min_tiles
                if tile_count >= min_tiles:
                    size = tile_count * self.tile_size_4bpp
                    tile_blocks.append((start, size, '4BPP'))
                    continue

            # Testa 2BPP
            elif self.is_bitplane_pattern(rom_data[i:i+self.tile_size_2bpp], bpp=2):
                start = i
                tile_count = 0

                while i < len(rom_data) - self.tile_size_2bpp:
                    if self.is_bitplane_pattern(rom_data[i:i+self.tile_size_2bpp], bpp=2):
                        tile_count += 1
                        i += self.tile_size_2bpp
                    else:
                        break

                if tile_count >= min_tiles:
                    size = tile_count * self.tile_size_2bpp
                    tile_blocks.append((start, size, '2BPP'))
                    continue

            i += 1

        return tile_blocks

    def extract_tiles_to_folder(self, rom_path: str, output_dir: str = "Laboratorio_Grafico") -> Dict:
        """
        Extrai todos os tiles gráficos para pasta separada.

        Returns:
            Dicionário com estatísticas da extração
        """
        # Lê ROM
        with open(rom_path, 'rb') as f:
            rom_data = f.read()

        # Cria diretório de saída
        base_dir = Path(rom_path).parent
        graphics_dir = base_dir / output_dir
        graphics_dir.mkdir(exist_ok=True)

        # Detecta blocos de tiles
        tile_blocks = self.detect_tile_blocks(rom_data)

        # Extrai cada bloco
        rom_name = Path(rom_path).stem
        stats = {
            'total_blocks': len(tile_blocks),
            'total_tiles_2bpp': 0,
            'total_tiles_4bpp': 0,
            'total_bytes': 0,
            'files_created': []
        }

        for idx, (offset, size, bpp_type) in enumerate(tile_blocks, 1):
            # Nome do arquivo
            filename = f"{rom_name}_tiles_{bpp_type}_{offset:08X}.bin"
            filepath = graphics_dir / filename

            # Extrai dados
            tile_data = rom_data[offset:offset+size]

            # Salva
            with open(filepath, 'wb') as f:
                f.write(tile_data)

            # Atualiza stats
            if bpp_type == '2BPP':
                stats['total_tiles_2bpp'] += size // self.tile_size_2bpp
            else:
                stats['total_tiles_4bpp'] += size // self.tile_size_4bpp

            stats['total_bytes'] += size
            stats['files_created'].append(str(filepath))

        # Salva índice de offsets
        index_file = graphics_dir / f"{rom_name}_tiles_index.txt"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write("# ÍNDICE DE TILES GRÁFICOS\n")
            f.write(f"# ROM: {rom_path}\n")
            f.write(f"# Total de blocos: {len(tile_blocks)}\n\n")

            for idx, (offset, size, bpp_type) in enumerate(tile_blocks, 1):
                tiles = size // (self.tile_size_2bpp if bpp_type == '2BPP' else self.tile_size_4bpp)
                f.write(f"Bloco {idx:03d}: Offset 0x{offset:08X} | {tiles} tiles | {bpp_type}\n")

        return stats


# ============================================================================
# 2. DETECTOR DE TABELA DE CARACTERES (TBL)
# ============================================================================

class CharTableDetector:
    """
    Auto-detecta se a ROM usa ASCII padrão ou uma tabela customizada.
    """

    def __init__(self):
        # Caracteres ASCII imprimíveis padrão
        self.ascii_printable = set(range(0x20, 0x7F))

        # Caracteres de controle comuns em ROMs
        self.control_chars = {0x00, 0xFF, 0xFE, 0xFD}

    def analyze_byte_distribution(self, rom_data: bytes, sample_size: int = 50000) -> Dict:
        """
        Analisa distribuição de bytes em regiões prováveis de texto.
        """
        # Pega amostra da ROM (evita header e regiões de código)
        start = min(0x8000, len(rom_data) // 4)
        sample = rom_data[start:start+sample_size]

        # Conta ocorrências
        byte_counts = Counter(sample)

        # Analisa padrões
        ascii_ratio = sum(byte_counts[b] for b in self.ascii_printable) / len(sample)
        control_ratio = sum(byte_counts[b] for b in self.control_chars) / len(sample)

        # Identifica bytes mais comuns (prováveis caracteres)
        common_bytes = byte_counts.most_common(30)

        return {
            'ascii_ratio': ascii_ratio,
            'control_ratio': control_ratio,
            'uses_ascii': ascii_ratio > 0.3,
            'common_bytes': common_bytes
        }

    def generate_custom_table(self, rom_data: bytes) -> Dict[int, str]:
        """
        Gera tabela customizada baseada em padrões identificados.
        """
        analysis = self.analyze_byte_distribution(rom_data)

        if analysis['uses_ascii']:
            # ROM usa ASCII padrão
            table = {b: chr(b) for b in range(0x20, 0x7F)}
        else:
            # ROM usa tabela customizada - mapeia bytes comuns
            table = {}

            # Mapeia caracteres de controle
            table[0x00] = ' '  # Espaço
            table[0xFF] = '\n'  # Nova linha
            table[0xFE] = '-'  # Hífen/separador

            # Mapeia letras comuns (heurística)
            # Bytes mais frequentes provavelmente são vogais e consoantes comuns
            common_chars = "etaoinshrdlcumwfgypbvkjxqz ETAOINSHRDLCUMWFGYPBVKJXQZ"

            for idx, (byte_val, count) in enumerate(analysis['common_bytes'][:52]):
                if byte_val not in self.control_chars and byte_val not in self.ascii_printable:
                    if idx < len(common_chars):
                        table[byte_val] = common_chars[idx]

        return table

    def decode_with_table(self, data: bytes, table: Dict[int, str]) -> str:
        """
        Decodifica bytes usando tabela fornecida.
        """
        result = []
        for byte in data:
            if byte in table:
                result.append(table[byte])
            else:
                # Caractere desconhecido - usa placeholder
                result.append(f"[{byte:02X}]")

        return ''.join(result)


# ============================================================================
# 3. FILTRO DE ENTROPIA SILÁBICA
# ============================================================================

class SyllabicEntropyFilter:
    """
    Filtra strings baseado em estrutura silábica humana.
    Texto real tem padrão vogal/consoante equilibrado.
    """

    def __init__(self):
        self.vowels = set('aeiouAEIOUáéíóúâêôãõ')
        self.consonants = set('bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ')

    def calculate_syllabic_score(self, text: str) -> float:
        """
        Calcula pontuação baseada em estrutura silábica.

        Critérios:
        - Proporção de vogais (ideal: 35-45%)
        - Alternância vogal/consoante
        - Ausência excessiva de caracteres de controle
        """
        if len(text) < 3:
            return 0.0

        # Remove caracteres de controle para análise
        clean_text = ''.join(c for c in text if c.isalpha() or c in ' -')

        if len(clean_text) < 3:
            return 0.0

        # Conta vogais e consoantes
        vowel_count = sum(1 for c in clean_text if c in self.vowels)
        consonant_count = sum(1 for c in clean_text if c in self.consonants)
        total_letters = vowel_count + consonant_count

        if total_letters == 0:
            return 0.0

        # Proporção de vogais (ideal: 40%)
        vowel_ratio = vowel_count / total_letters
        vowel_score = 100 if 0.30 <= vowel_ratio <= 0.50 else 50 * (1 - abs(0.40 - vowel_ratio))

        # Alternância vogal/consoante
        transitions = 0
        for i in range(len(clean_text) - 1):
            c1, c2 = clean_text[i], clean_text[i+1]
            if (c1 in self.vowels and c2 in self.consonants) or \
               (c1 in self.consonants and c2 in self.vowels):
                transitions += 1

        transition_ratio = transitions / max(1, len(clean_text) - 1)
        transition_score = min(100, transition_ratio * 200)

        # Penaliza excesso de caracteres de controle
        control_chars = sum(1 for c in text if c in '{}[]<>')
        control_penalty = max(0, 100 - (control_chars * 20))

        # Pontuação final (média ponderada)
        final_score = (vowel_score * 0.4 + transition_score * 0.4 + control_penalty * 0.2)

        return final_score

    def filter_strings(self, strings: List[str], min_score: float = 60.0) -> List[Tuple[str, float]]:
        """
        Filtra lista de strings baseado em pontuação silábica.

        Returns:
            Lista de (texto, pontuação) apenas para strings que passaram
        """
        filtered = []

        for text in strings:
            score = self.calculate_syllabic_score(text)
            if score >= min_score:
                filtered.append((text, score))

        # Ordena por pontuação (melhor primeiro)
        filtered.sort(key=lambda x: x[1], reverse=True)

        return filtered


# ============================================================================
# 4. DETECTOR DE PONTEIROS
# ============================================================================

class PointerDetector:
    """
    Identifica padrões repetitivos de 2-3 bytes que precedem blocos de texto.
    Ponteiros são usados para localizar strings na ROM.
    """

    def __init__(self):
        self.pointer_size = 2  # SNES usa ponteiros de 16-bit (2 bytes)

    def find_pointer_tables(self, rom_data: bytes, min_pointers: int = 8) -> List[Tuple[int, int]]:
        """
        Encontra tabelas de ponteiros na ROM.

        Tabela de ponteiros: sequência de endereços de 2 bytes consecutivos
        que apontam para regiões de texto.

        Returns:
            Lista de (offset_tabela, quantidade_ponteiros)
        """
        pointer_tables = []
        i = 0

        while i < len(rom_data) - (min_pointers * 2):
            # Lê sequência de possíveis ponteiros
            pointers = []
            j = i

            for _ in range(min_pointers * 2):  # Testa até 2x o mínimo
                if j + 2 > len(rom_data):
                    break

                ptr = struct.unpack('<H', rom_data[j:j+2])[0]  # Little-endian 16-bit
                pointers.append(ptr)
                j += 2

            # Verifica se é uma tabela válida
            if self.is_valid_pointer_table(pointers, rom_data):
                pointer_tables.append((i, len(pointers)))
                i = j  # Pula toda a tabela
            else:
                i += 1

        return pointer_tables

    def is_valid_pointer_table(self, pointers: List[int], rom_data: bytes) -> bool:
        """
        Verifica se uma sequência de valores é uma tabela de ponteiros válida.

        Critérios:
        - Ponteiros devem estar em ordem crescente (geralmente)
        - Ponteiros devem apontar para dentro da ROM
        - Regiões apontadas devem ter características de texto
        """
        if len(pointers) < 8:
            return False

        # Verifica ordem crescente (permite algumas exceções)
        ascending_count = sum(1 for i in range(len(pointers)-1) if pointers[i] < pointers[i+1])
        if ascending_count < len(pointers) * 0.7:  # 70% devem estar em ordem
            return False

        # Verifica se ponteiros estão dentro da ROM
        valid_range = sum(1 for ptr in pointers if 0 < ptr < len(rom_data))
        if valid_range < len(pointers) * 0.8:  # 80% devem estar válidos
            return False

        return True

    def extract_strings_from_pointers(self, rom_data: bytes, pointer_table_offset: int,
                                     num_pointers: int, table: Dict[int, str]) -> List[str]:
        """
        Extrai strings usando tabela de ponteiros.

        Args:
            pointer_table_offset: Offset da tabela de ponteiros
            num_pointers: Quantidade de ponteiros na tabela
            table: Tabela de caracteres para decodificação
        """
        strings = []

        for i in range(num_pointers):
            ptr_offset = pointer_table_offset + (i * 2)

            if ptr_offset + 2 > len(rom_data):
                break

            # Lê ponteiro
            ptr = struct.unpack('<H', rom_data[ptr_offset:ptr_offset+2])[0]

            if ptr >= len(rom_data):
                continue

            # Extrai string do endereço apontado
            text_data = rom_data[ptr:ptr+200]  # Lê até 200 bytes

            # Decodifica até encontrar terminador (0x00 ou 0xFF)
            decoded = []
            for byte in text_data:
                if byte in [0x00, 0xFF]:
                    break

                if byte in table:
                    decoded.append(table[byte])
                else:
                    decoded.append(f"[{byte:02X}]")

            if decoded:
                strings.append(''.join(decoded))

        return strings


# ============================================================================
# 5. NORMALIZADOR DE DELIMITADORES
# ============================================================================

class DelimiterNormalizer:
    """
    Normaliza bytes nulos e espaços para hífens, mantendo layout original.
    """

    def __init__(self):
        self.delimiter_bytes = {0x00, 0x20, 0xFE}  # NULL, SPACE, custom delimiter

    def normalize(self, text: str) -> str:
        """
        Converte sequências de espaços/nulos em hífens.

        Exemplos:
        'My  name' → 'My-name'
        'Press    START' → 'Press----START'
        """
        # Substitui múltiplos espaços por hífens
        import re

        # Substitui 2+ espaços por hífens equivalentes
        normalized = re.sub(r' {2,}', lambda m: '-' * len(m.group()), text)

        # Remove espaço único entre palavras curtas (< 3 letras)
        normalized = re.sub(r'\b(\w{1,2}) (\w{1,2})\b', r'\1-\2', normalized)

        return normalized


# ============================================================================
# 6. EXTRATOR AVANÇADO INTEGRADO
# ============================================================================

class AdvancedROMExtractor:
    """
    Sistema de extração completo integrando todos os componentes.
    """

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom_name = Path(rom_path).stem
        self.output_dir = Path(rom_path).parent

        # Inicializa componentes
        self.tile_detector = TileDetector()
        self.table_detector = CharTableDetector()
        self.syllabic_filter = SyllabicEntropyFilter()
        self.pointer_detector = PointerDetector()
        self.normalizer = DelimiterNormalizer()

        # Carrega ROM
        with open(rom_path, 'rb') as f:
            self.rom_data = f.read()

        # Auto-detecta tabela de caracteres
        self.char_table = self.table_detector.generate_custom_table(self.rom_data)

    def extract_all(self, export_tiles: bool = True) -> Dict:
        """
        Executa extração completa com todas as melhorias.

        Returns:
            Dicionário com estatísticas e caminhos dos arquivos gerados
        """
        print("="*80)
        print("🚀 ADVANCED ROM EXTRACTOR v2.0")
        print("="*80)
        print(f"\n📂 ROM: {self.rom_name}")
        print(f"📏 Tamanho: {len(self.rom_data):,} bytes\n")

        results = {
            'rom_path': self.rom_path,
            'rom_size': len(self.rom_data),
            'tiles_extracted': 0,
            'strings_found': 0,
            'high_quality_strings': 0,
            'files_created': []
        }

        # ETAPA 1: Separação de Tiles Gráficos
        if export_tiles:
            print("🎨 [1/5] Separando Tiles Gráficos...")
            tile_stats = self.tile_detector.extract_tiles_to_folder(self.rom_path)
            results['tiles_extracted'] = tile_stats['total_blocks']
            results['tiles_2bpp'] = tile_stats['total_tiles_2bpp']
            results['tiles_4bpp'] = tile_stats['total_tiles_4bpp']
            print(f"   ✅ {tile_stats['total_blocks']} blocos de tiles exportados")
            print(f"   📊 2BPP: {tile_stats['total_tiles_2bpp']} tiles | 4BPP: {tile_stats['total_tiles_4bpp']} tiles\n")

        # ETAPA 2: Detecção de Tabela de Caracteres
        print("🔤 [2/5] Detectando Tabela de Caracteres...")
        table_analysis = self.table_detector.analyze_byte_distribution(self.rom_data)
        uses_ascii = table_analysis['uses_ascii']
        print(f"   {'✅ ROM usa ASCII padrão' if uses_ascii else '⚙️ ROM usa tabela customizada'}\n")

        # ETAPA 3: Busca por Ponteiros
        print("🎯 [3/5] Detectando Tabelas de Ponteiros...")
        pointer_tables = self.pointer_detector.find_pointer_tables(self.rom_data)
        print(f"   ✅ {len(pointer_tables)} tabelas de ponteiros encontradas\n")

        # ETAPA 4: Extração de Strings
        print("📝 [4/5] Extraindo Strings...")
        all_strings = []

        # Extrai via ponteiros
        for table_offset, num_pointers in pointer_tables[:10]:  # Limita a 10 tabelas principais
            strings = self.pointer_detector.extract_strings_from_pointers(
                self.rom_data, table_offset, num_pointers, self.char_table
            )
            all_strings.extend(strings)

        # Remove duplicatas
        all_strings = list(set(all_strings))
        results['strings_found'] = len(all_strings)
        print(f"   ✅ {len(all_strings)} strings únicas extraídas\n")

        # ETAPA 5: Filtro de Qualidade Silábica
        print("🏅 [5/5] Aplicando Filtro de Qualidade Silábica...")
        filtered_strings = self.syllabic_filter.filter_strings(all_strings, min_score=60.0)
        results['high_quality_strings'] = len(filtered_strings)
        print(f"   ✅ {len(filtered_strings)} strings de alta qualidade\n")

        # NORMALIZAÇÃO: Converte delimitadores
        print("🔧 Normalizando delimitadores...")
        normalized_strings = [
            (self.normalizer.normalize(text), score)
            for text, score in filtered_strings
        ]

        # EXPORTAÇÃO: Salva resultados
        output_file = self.output_dir / f"{self.rom_name}_ADVANCED_EXTRACTED.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            for text, score in normalized_strings:
                f.write(f"{text}\n")

        results['files_created'].append(str(output_file))

        # Salva relatório detalhado
        report_file = self.output_dir / f"{self.rom_name}_EXTRACTION_REPORT.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("ADVANCED ROM EXTRACTOR - RELATÓRIO DETALHADO\n")
            f.write("="*80 + "\n\n")

            f.write(f"ROM: {self.rom_path}\n")
            f.write(f"Tamanho: {len(self.rom_data):,} bytes\n\n")

            f.write("TILES GRÁFICOS:\n")
            f.write(f"- Blocos exportados: {results.get('tiles_extracted', 0)}\n")
            f.write(f"- Tiles 2BPP: {results.get('tiles_2bpp', 0)}\n")
            f.write(f"- Tiles 4BPP: {results.get('tiles_4bpp', 0)}\n\n")

            f.write("TABELA DE CARACTERES:\n")
            f.write(f"- Tipo: {'ASCII Padrão' if uses_ascii else 'Tabela Customizada'}\n")
            f.write(f"- Taxa ASCII: {table_analysis['ascii_ratio']:.1%}\n\n")

            f.write("PONTEIROS:\n")
            f.write(f"- Tabelas encontradas: {len(pointer_tables)}\n\n")

            f.write("STRINGS EXTRAÍDAS:\n")
            f.write(f"- Total: {results['strings_found']}\n")
            f.write(f"- Alta qualidade: {results['high_quality_strings']}\n\n")

            f.write("="*80 + "\n")
            f.write("TOP 50 STRINGS (PONTUAÇÃO MAIS ALTA):\n")
            f.write("="*80 + "\n\n")

            for idx, (text, score) in enumerate(normalized_strings[:50], 1):
                f.write(f"{idx:3d}. [{score:5.1f}] {text}\n")

        results['files_created'].append(str(report_file))

        # RESUMO FINAL
        print("="*80)
        print("✅ EXTRAÇÃO CONCLUÍDA!")
        print("="*80)
        print(f"\n📊 RESUMO:")
        print(f"   🎨 Tiles exportados: {results.get('tiles_extracted', 0)}")
        print(f"   📝 Strings encontradas: {results['strings_found']}")
        print(f"   ⭐ Alta qualidade: {results['high_quality_strings']}")
        print(f"\n📂 ARQUIVOS GERADOS:")
        for filepath in results['files_created']:
            print(f"   - {Path(filepath).name}")
        print("\n" + "="*80 + "\n")

        return results


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def extract_rom_advanced(rom_path: str, export_tiles: bool = True) -> Dict:
    """
    Função principal para extração avançada de ROM.

    Args:
        rom_path: Caminho para o arquivo ROM
        export_tiles: Se True, exporta tiles gráficos para pasta separada

    Returns:
        Dicionário com estatísticas da extração
    """
    extractor = AdvancedROMExtractor(rom_path)
    return extractor.extract_all(export_tiles=export_tiles)


# ============================================================================
# EXECUÇÃO STANDALONE
# ============================================================================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        extract_rom_advanced(rom_path)
    else:
        print("Uso: python advanced_extractor.py <caminho_para_rom>")
        print("\nExemplo:")
        print('  python advanced_extractor.py "Super Mario World.smc"')
