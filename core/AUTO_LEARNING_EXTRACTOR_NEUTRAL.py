#!/usr/bin/env python3
"""
AUTO_LEARNING_EXTRACTOR.py - Sistema que APRENDE sozinho a extrair texto de QUALQUER jogo
NÃO precisa de configuração por jogo - descobre automaticamente!
"""

import os
import struct
import math
import hashlib
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import json

@dataclass
class LearnedPattern:
    """Padrões aprendidos sobre um jogo"""
    rom_hash: str
    game_name: str
    text_offsets: List[int]
    terminator_bytes: List[int]
    char_mapping: Dict[int, str]
    pointer_patterns: List[int]
    compression_type: Optional[str]
    confidence: float

class AutoLearningExtractor:
    """Extrator que aprende automaticamente com cada ROM"""
    
    def __init__(self):
        self.learned_games: Dict[str, LearnedPattern] = {}
        self.base_tables = self._load_base_tables()
        self.load_learned_data()
        
        # Estatísticas de aprendizado
        self.stats = {
            'games_processed': 0,
            'patterns_learned': 0,
            'success_rate': 0.0
        }
    
    def _load_base_tables(self) -> Dict[str, Dict[int, str]]:
        """Carrega tabelas base para iniciar o aprendizado"""
        return {
            'ASCII': {i: chr(i) for i in range(32, 127)},
            'SEGA_BASIC': self._get_sega_basic(),
            'SONIC_LIKE': self._get_sonic_like(),
            'DISNEY_LIKE': self._get_disney_like(),
            'JAPANESE_LIKE': self._get_japanese_like(),
        }
    
    def _get_sega_basic(self) -> Dict[int, str]:
        """Tabela Sega básica expandida"""
        table = {}
        for i in range(32, 127):
            table[i] = chr(i)
        
        # Controles comuns
        controls = {
            0x00: '[END]', 0x01: '[NL]', 0x02: '[SCORE]', 0x03: '[TIME]',
            0x04: '[LIVES]', 0x05: '[RINGS]', 0x06: '[CONTINUE]', 0x07: '[GAME]',
            0x08: '[OVER]', 0x09: '[PAUSE]', 0x0A: '[STAGE]', 0x0B: '[ACT]',
            0x0C: '[ZONE]', 0x0D: '\n', 0x0E: '[NAME]', 0x0F: '[ITEM]',
            0xFF: '[END2]'
        }
        table.update(controls)
        
        # Caracteres especiais comuns
        specials = {
            0x80: 'Á', 0x81: 'É', 0x82: 'Í', 0x83: 'Ó', 0x84: 'Ú',
            0x85: 'À', 0x86: 'È', 0x87: 'Ì', 0x88: 'Ò', 0x89: 'Ù',
            0x8A: 'Â', 0x8B: 'Ê', 0x8C: 'Î', 0x8D: 'Ô', 0x8E: 'Û',
            0x8F: 'Ä', 0x90: 'Ë', 0x91: 'Ï', 0x92: 'Ö', 0x93: 'Ü',
            0x94: 'Ç', 0x95: 'Ñ', 0x96: '¡', 0x97: '¿',
            0xA0: '©', 0xA1: '™', 0xA2: '®', 0xA3: '♥',
            0xA4: '♦', 0xA5: '♣', 0xA6: '♠', 0xA7: '•',
            0xA8: '○', 0xA9: '●', 0xAA: '★', 0xAB: '☆',
            0xAC: '▲', 0xAD: '▼', 0xAE: '►', 0xAF: '◄',
        }
        table.update(specials)
        
        return table
    
    def _get_sonic_like(self) -> Dict[int, str]:
        """Tabela estilo Sonic (jogos Sega)"""
        table = self._get_sega_basic().copy()
        # Ajustes específicos para jogos tipo Sonic
        sonic_adj = {
            0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3',
            0x34: '4', 0x35: '5', 0x36: '6', 0x37: '7',
            0x38: '8', 0x39: '9',
            0x40: 'A', 0x41: 'B', 0x42: 'C', 0x43: 'D',
            0x44: 'E', 0x45: 'F', 0x46: 'G', 0x47: 'H',
            0x48: 'I', 0x49: 'J', 0x4A: 'K', 0x4B: 'L',
            0x4C: 'M', 0x4D: 'N', 0x4E: 'O', 0x4F: 'P',
            0x50: 'Q', 0x51: 'R', 0x52: 'S', 0x53: 'T',
            0x54: 'U', 0x55: 'V', 0x56: 'W', 0x57: 'X',
            0x58: 'Y', 0x59: 'Z',
        }
        table.update(sonic_adj)
        return table
    
    def _get_disney_like(self) -> Dict[int, str]:
        """Tabela estilo Disney (jogos com gráficos mais elaborados)"""
        table = self._get_sega_basic().copy()
        # Disney geralmente usa ASCII normal, mas com caracteres especiais
        return table
    
    def _get_japanese_like(self) -> Dict[int, str]:
        """Tabela para jogos japoneses"""
        table = {}
        # Katakana básico
        katakana = {
            0x80: 'ア', 0x81: 'イ', 0x82: 'ウ', 0x83: 'エ', 0x84: 'オ',
            0x85: 'カ', 0x86: 'キ', 0x87: 'ク', 0x88: 'ケ', 0x89: 'コ',
            0x8A: 'サ', 0x8B: 'シ', 0x8C: 'ス', 0x8D: 'セ', 0x8E: 'ソ',
            0x8F: 'タ', 0x90: 'チ', 0x91: 'ツ', 0x92: 'テ', 0x93: 'ト',
            0x94: 'ナ', 0x95: 'ニ', 0x96: 'ヌ', 0x97: 'ネ', 0x98: 'ノ',
            0x99: 'ハ', 0x9A: 'ヒ', 0x9B: 'フ', 0x9C: 'ヘ', 0x9D: 'ホ',
            0x9E: 'マ', 0x9F: 'ミ', 0xA0: 'ム', 0xA1: 'メ', 0xA2: 'モ',
            0xA3: 'ヤ', 0xA4: 'ユ', 0xA5: 'ヨ',
            0xA6: 'ラ', 0xA7: 'リ', 0xA8: 'ル', 0xA9: 'レ', 0xAA: 'ロ',
            0xAB: 'ワ', 0xAC: 'ヲ', 0xAD: 'ン',
            0xC7: '。', 0xC8: '、', 0xC9: '・', 0xCA: 'ー',
            0xCB: '「', 0xCC: '」', 0xCD: '！', 0xCE: '？',
        }
        table.update(katakana)
        
        # Adiciona ASCII
        for i in range(32, 127):
            table[i] = chr(i)
        
        # Controles
        table[0x00] = '[END]'
        table[0x01] = '[NL]'
        table[0xFF] = '[END2]'
        
        return table
    
    def load_learned_data(self):
        """Carrega dados aprendidos de sessões anteriores"""
        try:
            with open('auto_learned_patterns.json', 'r') as f:
                data = json.load(f)
                for game_hash, game_data in data.items():
                    self.learned_games[game_hash] = LearnedPattern(
                        rom_hash=game_data['rom_hash'],
                        game_name=game_data['game_name'],
                        text_offsets=game_data['text_offsets'],
                        terminator_bytes=game_data['terminator_bytes'],
                        char_mapping=game_data['char_mapping'],
                        pointer_patterns=game_data['pointer_patterns'],
                        compression_type=game_data.get('compression_type'),
                        confidence=game_data['confidence']
                    )
            print(f"📚 Dados aprendidos carregados: {len(self.learned_games)} jogos")
        except FileNotFoundError:
            print("📚 Nenhum dado aprendido encontrado. Começando do zero.")
    
    def save_learned_data(self):
        """Salva dados aprendidos para uso futuro"""
        data = {}
        for game_hash, pattern in self.learned_games.items():
            data[game_hash] = {
                'rom_hash': pattern.rom_hash,
                'game_name': pattern.game_name,
                'text_offsets': pattern.text_offsets,
                'terminator_bytes': pattern.terminator_bytes,
                'char_mapping': pattern.char_mapping,
                'pointer_patterns': pattern.pointer_patterns,
                'compression_type': pattern.compression_type,
                'confidence': pattern.confidence
            }
        
        with open('auto_learned_patterns.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Dados aprendidos salvos: {len(self.learned_games)} jogos")
    
    def _crc32_file(self, rom_path: str) -> Tuple[str, int]:
        """Calcula CRC32 (full) e tamanho do arquivo.

        Neutralidade V1: identificação por CRC32 e tamanho, nunca por nome do arquivo.
        """
        crc = 0
        size = 0
        with open(rom_path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08X}", size

    def analyze_rom(self, rom_path: str) -> Tuple[str, bytes]:
        """Analisa a ROM e retorna hash e dados"""
        with open(rom_path, 'rb') as f:
            rom_data = f.read()
        rom_hash = hashlib.md5(rom_data).hexdigest()
        # Neutralidade V1: não usar nome do arquivo como identificação
        crc32_full, rom_size = self._crc32_file(rom_path)
        print(f"🔍 Analisando ROM | CRC32={crc32_full} | ROM_SIZE={rom_size} bytes")
        print(f"   Hash: {rom_hash}")
        print(f"   Tamanho: {len(rom_data):,} bytes")
        return rom_hash, rom_data
    
    def discover_text_patterns(self, rom_data: bytes) -> LearnedPattern:
        """Descobre padrões de texto automaticamente"""
        print("🧠 Descobrindo padrões de texto...")
        terminators = self._find_terminators(rom_data)
        text_regions = self._find_text_regions(rom_data, terminators)
        char_mapping = self._learn_char_mapping(rom_data, text_regions)
        pointer_patterns = self._find_pointer_patterns(rom_data)
        compression_type = self._detect_compression(rom_data)
        confidence = self._calculate_confidence(
            len(text_regions), 
            len(char_mapping),
            len(pointer_patterns)
        )
        pattern = LearnedPattern(
            rom_hash="",
            game_name="",
            text_offsets=[r[0] for r in text_regions[:100]],
            terminator_bytes=terminators,
            char_mapping=char_mapping,
            pointer_patterns=pointer_patterns[:20],
            compression_type=compression_type,
            confidence=confidence
        )
        return pattern
    
    def _find_terminators(self, rom_data: bytes) -> List[int]:
        """Encontra bytes que provavelmente terminam strings"""
        freq = Counter(rom_data)
        terminators = []
        for byte, count in freq.most_common(50):
            if byte in [0x00, 0xFF, 0xFE, 0xFD, 0xFC, 0xFB]:
                terminators.append(byte)
            elif count > len(rom_data) * 0.001 and byte < 0x20:
                terminators.append(byte)
        if len(terminators) < 3:
            terminators.extend([0x00, 0xFF, 0xFE])
        return list(set(terminators))[:5]
    
    def _find_text_regions(self, rom_data: bytes, terminators: List[int]) -> List[Tuple[int, int]]:
        """Encontra regiões que provavelmente contêm texto"""
        regions = []
        i = 0
        while i < len(rom_data):
            if rom_data[i] in terminators:
                i += 1
                continue
            start = i
            text_length = 0
            printable_count = 0
            while i < len(rom_data) and rom_data[i] not in terminators:
                byte = rom_data[i]
                if self._looks_printable(byte):
                    printable_count += 1
                text_length += 1
                i += 1
                if text_length > 200:
                    break
            if text_length >= 3 and printable_count / text_length > 0.6:
                regions.append((start, text_length))
            i += 1
        return regions[:500]
    
    def _looks_printable(self, byte: int) -> bool:
        """Verifica se um byte parece ser caractere imprimível"""
        if 0x20 <= byte <= 0x7E:
            return True
        if byte in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 
                   0x08, 0x09, 0x0A, 0x0D, 0xFF]:
            return True
        if byte >= 0x80:
            return True
        return False
    
    def _learn_char_mapping(self, rom_data: bytes, regions: List[Tuple[int, int]]) -> Dict[int, str]:
        """Aprende mapeamento de caracteres automaticamente"""
        print("   Aprendendo mapeamento de caracteres...")
        text_bytes = []
        for start, length in regions[:100]:
            end = min(start + length, len(rom_data))
            text_bytes.extend(rom_data[start:end])
        if not text_bytes:
            return self.base_tables['ASCII'].copy()
        freq = Counter(text_bytes)
        mappings = []
        ascii_mapping = {}
        ascii_score = 0
        for byte, count in freq.most_common(100):
            if 0x20 <= byte <= 0x7E:
                ascii_mapping[byte] = chr(byte)
                ascii_score += count
        mappings.append(('ASCII', ascii_mapping, ascii_score))
        for offset in range(-10, 11):
            if offset == 0:
                continue
            shifted_mapping = {}
            shifted_score = 0
            for byte, count in freq.most_common(100):
                mapped_byte = byte + offset
                if 0x20 <= mapped_byte <= 0x7E:
                    shifted_mapping[byte] = chr(mapped_byte)
                    shifted_score += count
            if shifted_score > ascii_score * 0.8:
                mappings.append((f'SHIFT_{offset}', shifted_mapping, shifted_score))
        best_name, best_mapping, best_score = max(mappings, key=lambda x: x[2])
        print(f"   Melhor mapeamento: {best_name} (score: {best_score})")
        best_mapping[0x00] = '[END]'
        best_mapping[0xFF] = '[END2]'
        best_mapping[0x0A] = '\n'
        best_mapping[0x0D] = '\r'
        return best_mapping
    
    def _find_pointer_patterns(self, rom_data: bytes) -> List[int]:
        """Encontra padrões de ponteiros"""
        patterns = []
        for i in range(0, len(rom_data) - 8, 2):
            pointers = []
            for j in range(4):
                pos = i + (j * 2)
                if pos + 2 <= len(rom_data):
                    ptr = struct.unpack_from('<H', rom_data, pos)[0]
                    if 0x4000 <= ptr <= 0xFFFF:
                        pointers.append(ptr)
            if len(pointers) >= 3:
                if pointers == sorted(pointers):
                    patterns.append(i)
            if len(patterns) >= 20:
                break
        return patterns
    
    def _detect_compression(self, rom_data: bytes) -> Optional[str]:
        """Detecta tipo de compressão"""
        signatures = {
            b'\x10': 'LZ77',
            b'\x20': 'RLE',
            b'\x30': 'NEMESIS',
            b'\x4C\x5A': 'LZSS',
            b'\xEA': 'EA_COMPRESSION',
        }
        for sig, name in signatures.items():
            if rom_data.count(sig) > 3:
                return name
        return None
    
    def _calculate_confidence(self, regions: int, chars: int, pointers: int) -> float:
        """Calcula confiança nos padrões descobertos"""
        region_score = min(regions / 10, 1.0)
        char_score = min(chars / 50, 1.0)
        pointer_score = min(pointers / 5, 1.0)
        confidence = (region_score * 0.4 + char_score * 0.4 + pointer_score * 0.2)
        return round(confidence, 2)
    
    def extract_texts(self, rom_data: bytes, pattern: LearnedPattern) -> List[Tuple[int, str]]:
        """Extrai textos usando os padrões aprendidos"""
        print("📝 Extraindo textos...")
        all_texts = []
        for start, length in pattern.text_offsets[:50]:
            if start < len(rom_data):
                text = self._extract_string(rom_data, start, pattern)
                if text and len(text.strip()) > 1:
                    all_texts.append((start, text))
        for ptr_table in pattern.pointer_patterns[:10]:
            pointer_texts = self._extract_from_pointers(rom_data, ptr_table, pattern)
            all_texts.extend(pointer_texts)
        additional_texts = self._find_additional_texts(rom_data, pattern)
        all_texts.extend(additional_texts)
        unique_texts = {}
        for addr, text in all_texts:
            if text and text not in unique_texts:
                unique_texts[text] = addr
        result = [(addr, text) for text, addr in unique_texts.items()]
        result.sort(key=lambda x: x[0])
        return result
    
    def _extract_string(self, rom_data: bytes, start: int, pattern: LearnedPattern) -> str:
        """Extrai uma string usando os terminadores aprendidos"""
        result = []
        i = start
        while i < len(rom_data):
            byte = rom_data[i]
            if byte in pattern.terminator_bytes:
                break
            if byte in pattern.char_mapping:
                result.append(pattern.char_mapping[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1
            if i - start > 200:
                break
        return ''.join(result)
    
    def _extract_from_pointers(self, rom_data: bytes, table_start: int, pattern: LearnedPattern) -> List[Tuple[int, str]]:
        """Extrai textos seguindo ponteiros"""
        texts = []
        for i in range(0, 100, 2):
            ptr_pos = table_start + i
            if ptr_pos + 2 > len(rom_data):
                break
            pointer = struct.unpack_from('<H', rom_data, ptr_pos)[0]
            if 0x8000 <= pointer <= 0xFFFF:
                rom_offset = pointer - 0x8000
            elif 0x4000 <= pointer < 0x8000:
                rom_offset = pointer - 0x4000
            else:
                continue
            if rom_offset < len(rom_data):
                text = self._extract_string(rom_data, rom_offset, pattern)
                if text and len(text.strip()) > 1:
                    texts.append((rom_offset, text))
        return texts
    
    def _find_additional_texts(self, rom_data: bytes, pattern: LearnedPattern) -> List[Tuple[int, str]]:
        """Encontra textos adicionais usando heurísticas"""
        texts = []
        i = 0
        while i < len(rom_data) - 10:
            byte = rom_data[i]
            if byte in pattern.char_mapping and pattern.char_mapping[byte] not in ['[END]', '[END2]']:
                text = self._extract_string(rom_data, i, pattern)
                if text and len(text.replace('[', '').replace(']', '').strip()) > 2:
                    if any(c.isalpha() for c in text):
                        texts.append((i, text))
                        i += len(text)
                        continue
            i += 1
        return texts
    
    def process_game(self, rom_path: str) -> List[Tuple[int, str]]:
        """Processa um jogo completo (análise + extração)"""
        # Neutralidade V1: identificação por CRC32 e tamanho, não por nome do arquivo
        crc32_full, rom_size = self._crc32_file(rom_path)
        print("\n" + "=" * 60)
        print(f"🎮 PROCESSANDO: CRC32={crc32_full} | ROM_SIZE={rom_size} bytes")
        print("=" * 60)
        rom_hash, rom_data = self.analyze_rom(rom_path)
        if rom_hash in self.learned_games:
            print("📚 Usando padrões já aprendidos!")
            pattern = self.learned_games[rom_hash]
        else:
            pattern = self.discover_text_patterns(rom_data)
            pattern.rom_hash = rom_hash
            # Neutralidade V1: não armazenar nome do arquivo
            pattern.game_name = ""
            self.learned_games[rom_hash] = pattern
            self.stats['patterns_learned'] += 1
        texts = self.extract_texts(rom_data, pattern)
        print(f"✅ Extraídos {len(texts)} textos (Confiança: {pattern.confidence*100:.0f}%)")
        if texts:
            print("\n📄 PRÉVIA DOS TEXTOS:")
            print("-" * 40)
            for i, (addr, text) in enumerate(texts[:10], 1):
                print(f"{i:2d}. 0x{addr:06X}: {text[:50]}{'...' if len(text) > 50 else ''}")
        self.stats['games_processed'] += 1
        success_rate = len(texts) / max(1, len(texts))
        self.stats['success_rate'] = (self.stats['success_rate'] + success_rate) / 2
        return texts
    
    def batch_process(self, rom_folder: str):
        """Processa TODAS as ROMs de uma pasta automaticamente"""
        print("=" * 70)
        print("🤖 BATCH PROCESSING - Processando TODAS as ROMs")
        print("=" * 70)
        rom_extensions = ['.sms', '.gg', '.bin']
        rom_files = []
        for root, dirs, files in os.walk(rom_folder):
            for file in files:
                if any(file.lower().endswith(ext) for ext in rom_extensions):
                    rom_files.append(os.path.join(root, file))
        print(f"📁 Encontradas {len(rom_files)} ROMs para processar")
        results = {}
        for i, rom_path in enumerate(rom_files, 1):
            try:
                print(f"\n[{i}/{len(rom_files)}] ", end="")
                texts = self.process_game(rom_path)
                results[rom_path] = texts
                self.save_learned_data()
            except Exception as e:
                print(f"❌ Erro ao processar {rom_path}: {e}")
                continue
        self.generate_report(results)
        return results
    
    def generate_report(self, results: Dict[str, List[Tuple[int, str]]]):
        """Gera relatório de processamento"""
        report_file = "auto_extractor_report.txt"
        total_games = len(results)
        total_texts = sum(len(texts) for texts in results.values())
        avg_texts = total_texts / max(1, total_games)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RELATÓRIO DO AUTO-LEARNING EXTRACTOR\n")
            f.write("=" * 80 + "\n\n")
            f.write("📊 ESTATÍSTICAS GERAIS:\n")
            f.write(f"   • Jogos processados: {total_games}\n")
            f.write(f"   • Textos extraídos: {total_texts}\n")
            f.write(f"   • Média por jogo: {avg_texts:.1f} textos\n")
            f.write(f"   • Padrões aprendidos: {len(self.learned_games)}\n")
            f.write(f"   • Taxa de sucesso: {self.stats['success_rate']*100:.1f}%\n\n")
            f.write("🎮 JOGOS PROCESSADOS:\n")
            f.write("-" * 40 + "\n")
            for rom_path, texts in results.items():
                crc32_full, _ = self._crc32_file(rom_path)
                f.write(f"\nCRC32={crc32_full}:\n")
                f.write(f"  • Textos: {len(texts)}\n")
                rom_hash = hashlib.md5(open(rom_path, 'rb').read()).hexdigest()
                if rom_hash in self.learned_games:
                    pattern = self.learned_games[rom_hash]
                    f.write(f"  • Confiança: {pattern.confidence*100:.0f}%\n")
                    f.write(f"  • Terminadores: {[f'0x{b:02X}' for b in pattern.terminator_bytes]}\n")
                    if pattern.compression_type:
                        f.write(f"  • Compressão: {pattern.compression_type}\n")
                if texts:
                    f.write(f"  • Exemplos:\n")
                    for addr, text in texts[:3]:
                        f.write(f"    0x{addr:06X}: {text[:40]}{'...' if len(text) > 40 else ''}\n")
        print(f"\n📊 RELATÓRIO GERADO: {report_file}")
        json_data = {}
        for rom_path, texts in results.items():
            crc32_full, _ = self._crc32_file(rom_path)
            json_data[crc32_full] = [
                {"address": f"0x{addr:06X}", "text": text}
                for addr, text in texts
            ]
        with open('all_extracted_texts.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"📁 Todos os textos salvos em: all_extracted_texts.json")
        print(f"💾 Padrões aprendidos salvos em: auto_learned_patterns.json")
    
    def interactive_mode(self):
        """Modo interativo para processar ROMs individualmente"""
        print("=" * 70)
        print("🎮 MODO INTERATIVO - AUTO-LEARNING EXTRACTOR")
        print("=" * 70)
        while True:
            print("\n📂 Opções:")
            print("1. Processar uma ROM específica")
            print("2. Processar TODAS as ROMs de uma pasta")
            print("3. Ver estatísticas de aprendizado")
            print("4. Limpar dados aprendidos")
            print("5. Sair")
            choice = input("\nEscolha (1-5): ").strip()
            if choice == "1":
                rom_path = input("Caminho da ROM: ").strip()
                if os.path.exists(rom_path):
                    texts = self.process_game(rom_path)
                    save = input(f"\n💾 Salvar {len(texts)} textos? (s/n): ").strip().lower()
                    if save == 's':
                        # Neutralidade V1: nome de arquivo baseado em CRC32
                        crc32_full, _ = self._crc32_file(rom_path)
                        output_file = f"{crc32_full}_texts.txt"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            for addr, text in texts:
                                f.write(f"0x{addr:06X}: {text}\n")
                        print(f"✅ Textos salvos em: {output_file}")
                else:
                    print("❌ Arquivo não encontrado!")
            elif choice == "2":
                folder = input("Pasta com ROMs: ").strip()
                if os.path.exists(folder):
                    self.batch_process(folder)
                else:
                    print("❌ Pasta não encontrada!")
            elif choice == "3":
                print(f"\n📊 ESTATÍSTICAS:")
                print(f"   • Jogos processados: {self.stats['games_processed']}")
                print(f"   • Padrões aprendidos: {len(self.learned_games)}")
                print(f"   • Taxa de sucesso: {self.stats['success_rate']*100:.1f}%")
                if self.learned_games:
                    print(f"\n🎮 JOGOS APRENDIDOS:")
                    for game_hash, pattern in list(self.learned_games.items())[:10]:
                        # Neutralidade V1: exibir apenas hash (CRC32), não nome do arquivo
                        print(f"   • Hash={pattern.rom_hash[:16]:16} (Conf: {pattern.confidence*100:.0f}%)")
                    if len(self.learned_games) > 10:
                        print(f"   ... e mais {len(self.learned_games) - 10} jogos")
            elif choice == "4":
                confirm = input("⚠️  Tem certeza que quer limpar TODOS os dados aprendidos? (s/n): ").strip().lower()
                if confirm == 's':
                    self.learned_games = {}
                    if os.path.exists('auto_learned_patterns.json'):
                        os.remove('auto_learned_patterns.json')
                    print("✅ Dados aprendidos limpos!")
            elif choice == "5":
                print("\n👋 Até mais! Dados salvos automaticamente.")
                self.save_learned_data()
                break

def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║   AUTO-LEARNING EXTRACTOR v2.0                   ║
    ║   Descobre sozinho como extrair texto            ║
    ║   de QUALQUER jogo do Master System!            ║
    ╚══════════════════════════════════════════════════╝
    """)
    extractor = AutoLearningExtractor()
    print("🔍 Procurando ROMs na pasta atual...")
    roms_found = []
    for file in os.listdir('.'):
        if file.lower().endswith(('.sms', '.gg', '.bin')):
            roms_found.append(file)
    if roms_found:
        print(f"📁 Encontradas {len(roms_found)} ROMs:")
        for rom in roms_found:
            print(f"   • {rom}")
        auto_process = input("\n🤖 Processar todas automaticamente? (s/n): ").strip().lower()
        if auto_process == 's':
            extractor.batch_process('.')
        else:
            extractor.interactive_mode()
    else:
        print("❌ Nenhuma ROM encontrada na pasta atual.")
        print("💡 Coloque algumas ROMs (.sms, .gg, .bin) aqui e execute novamente.")
        use_interactive = input("\n🎮 Usar modo interativo mesmo assim? (s/n): ").strip().lower()
        if use_interactive == 's':
            extractor.interactive_mode()

if __name__ == "__main__":
    main()