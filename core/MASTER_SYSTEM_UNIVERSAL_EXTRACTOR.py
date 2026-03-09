# -*- coding: utf-8 -*-
"""
MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py

Extrator universal para ROMs do Sega Master System.
- Detecta jogo automaticamente por assinatura (não pelo nome)
- Banco de dados de tabelas de caracteres por jogo
- Fallback para ASCII quando não reconhecer
- Fácil adicionar novas tabelas
"""

import json
import re
import hashlib
from pathlib import Path


# =====================================================
# BANCO DE DADOS DE TABELAS DE CARACTERES
# Adicione novas tabelas aqui conforme documentar jogos
# =====================================================

CHAR_TABLES = {

    # -------------------------
    # GAME_001 - Sonic The Hedgehog (SMS)
    # -------------------------
    "game_001": {
        "name": "Sonic The Hedgehog (Master System)",
        "signatures": [
            {"offset": 0x7FF0, "bytes": b"TMR SEGA"},
            {"offset": 0x0000, "bytes": b"\xF3\xED\x56\xC3"},  # Início comum em alguns dumps
        ],
        # CRCs conhecidos (full ROM ou ROM sem header de 512 bytes)
        "crc32": ["B519E833", "3B3EE2F6", "1B10E390"],

        # O Sonic usa mais de um tilemap/tabela dependendo da tela.
        # MAP1: tela do mapa 1 (Green Hill/Bridge/Jungle) e Score Titles
        # MAP2: tela do mapa 2 (Labyrinth/Scrap Brain/Sky Base) e Credits
        "tables": {
            "map1": {
                0xEB: ' ',
                0xCF: '©',
                0x34: 'A', 0x35: 'B', 0x36: 'C', 0x37: 'D',
                0x44: 'E', 0x45: 'F', 0x46: 'G', 0x47: 'H',
                0x40: 'I', 0x41: 'J', 0x42: 'K', 0x43: 'L',
                0x50: 'M', 0x51: 'N', 0x52: 'O', 0x60: 'P',
                0x61: 'Q', 0x62: 'R', 0x70: 'S', 0x80: 'T',
                0x81: 'U', 0x54: 'V', 0x3C: 'W', 0x3D: 'X',
                0x3E: 'Y', 0x3F: 'Z',
            },
            "map2": {
                0xEB: ' ',
                0xAB: '©',
                0x1E: 'A', 0x1F: 'B', 0x2E: 'C', 0x2F: 'D',
                0x3E: 'E', 0x3F: 'F', 0x4E: 'G', 0x4F: 'H',
                0x5E: 'I', 0x5F: 'J', 0x6E: 'K', 0x6F: 'L',
                0x7E: 'M', 0x7F: 'N', 0x8E: 'O', 0x8F: 'P',
                0x9E: 'Q', 0x9F: 'R', 0xAE: 'S', 0xAF: 'T',
                0xBE: 'U', 0xBF: 'V', 0xCE: 'W', 0xCF: 'X',
                0xDE: 'Y', 0xDF: 'Z',
            }
        },
        "default_table": "map1",

        "terminator": 0xFF,
        "commands": {0xFE: 2, 0xFD: 2, 0xFC: 1},
        "text_regions": [
            {"name": "Zone Titles", "start": 0x0122D, "end": 0x01286, "skip": 2, "tables": ["map1", "map2"]},
            {"name": "Score Titles", "start": 0x0197E, "end": 0x019AD, "skip": 2, "tables": ["map1"]},
            {"name": "Credits", "start": 0x02905, "end": 0x02AD5, "skip": 2, "tables": ["map2"], "max_len": 8000},
        ]
    },

    # -------------------------
    # GAME_002 - Adventure Platformer
    # -------------------------
    "game_002": {
        "name": "Adventure Platformer",
        "signatures": [
            {"offset": 0x7FF0, "bytes": b"TMR SEGA"},
        ],
        "crc32": ["17A40E29", "9AA26C78"],
        "table": {
            # Alex Kidd usa encoding diferente
            0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D',
            0x05: 'E', 0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I',
            0x0A: 'J', 0x0B: 'K', 0x0C: 'L', 0x0D: 'M', 0x0E: 'N',
            0x0F: 'O', 0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S',
            0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W', 0x18: 'X',
            0x19: 'Y', 0x1A: 'Z', 0x1B: '0', 0x1C: '1', 0x1D: '2',
            0x1E: '3', 0x1F: '4', 0x20: '5', 0x21: '6', 0x22: '7',
            0x23: '8', 0x24: '9', 0x25: '.', 0x26: ',', 0x27: '!',
            0x28: '?', 0x29: "'", 0x2A: '-',
        },
        "terminator": 0xFF,
        "commands": {},
        "text_regions": []
    },

    # -------------------------
    # GAME_003 - Side Scroller
    # -------------------------
    "game_003": {
        "name": "Side Scroller",
        "signatures": [
            {"offset": 0x7FF0, "bytes": b"TMR SEGA"},
        ],
        "crc32": ["9E9B0B90", "73705B9B"],
        "table": {
            0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D',
            0x05: 'E', 0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I',
            0x0A: 'J', 0x0B: 'K', 0x0C: 'L', 0x0D: 'M', 0x0E: 'N',
            0x0F: 'O', 0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S',
            0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W', 0x18: 'X',
            0x19: 'Y', 0x1A: 'Z', 0x1B: '0', 0x1C: '1', 0x1D: '2',
            0x1E: '3', 0x1F: '4', 0x20: '5', 0x21: '6', 0x22: '7',
            0x23: '8', 0x24: '9',
        },
        "terminator": 0xFF,
        "commands": {},
        "text_regions": []
    },

    # -------------------------
    # GAME_004 - RPG Classic
    # -------------------------
    "game_004": {
        "name": "RPG Classic",
        "signatures": [
            {"offset": 0x7FF0, "bytes": b"TMR SEGA"},
        ],
        "crc32": ["E4A65E79", "6605D36A"],
        "table": {
            # Phantasy Star tem encoding próprio para diálogos
            0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D',
            0x05: 'E', 0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I',
            0x0A: 'J', 0x0B: 'K', 0x0C: 'L', 0x0D: 'M', 0x0E: 'N',
            0x0F: 'O', 0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S',
            0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W', 0x18: 'X',
            0x19: 'Y', 0x1A: 'Z', 0x1B: 'a', 0x1C: 'b', 0x1D: 'c',
            0x1E: 'd', 0x1F: 'e', 0x20: 'f', 0x21: 'g', 0x22: 'h',
            0x23: 'i', 0x24: 'j', 0x25: 'k', 0x26: 'l', 0x27: 'm',
            0x28: 'n', 0x29: 'o', 0x2A: 'p', 0x2B: 'q', 0x2C: 'r',
            0x2D: 's', 0x2E: 't', 0x2F: 'u', 0x30: 'v', 0x31: 'w',
            0x32: 'x', 0x33: 'y', 0x34: 'z', 0x35: '0', 0x36: '1',
            0x37: '2', 0x38: '3', 0x39: '4', 0x3A: '5', 0x3B: '6',
            0x3C: '7', 0x3D: '8', 0x3E: '9', 0x3F: '.', 0x40: ',',
            0x41: '!', 0x42: '?', 0x43: "'", 0x44: '-', 0x45: ':',
        },
        "terminator": 0xFF,
        "commands": {0xFE: 1, 0xFD: 1},
        "text_regions": []
    },

    # -------------------------
    # GAME_005 - Disney Platformer
    # -------------------------
    "game_005": {
        "name": "Disney Platformer",
        "signatures": [
            {"offset": 0x7FF0, "bytes": b"TMR SEGA"},
        ],
        "crc32": ["9942B69B"],
        "table": {
            0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D',
            0x05: 'E', 0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I',
            0x0A: 'J', 0x0B: 'K', 0x0C: 'L', 0x0D: 'M', 0x0E: 'N',
            0x0F: 'O', 0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S',
            0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W', 0x18: 'X',
            0x19: 'Y', 0x1A: 'Z',
        },
        "terminator": 0xFF,
        "commands": {},
        "text_regions": []
    },

    # -------------------------
    # GAME_006 - Action RPG
    # -------------------------
    "game_006": {
        "name": "Action RPG",
        "signatures": [],
        "crc32": ["53588E6D"],
        "table": {
            0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D',
            0x05: 'E', 0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I',
            0x0A: 'J', 0x0B: 'K', 0x0C: 'L', 0x0D: 'M', 0x0E: 'N',
            0x0F: 'O', 0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S',
            0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W', 0x18: 'X',
            0x19: 'Y', 0x1A: 'Z',
        },
        "terminator": 0x00,
        "commands": {},
        "text_regions": []
    },
}

# Tabela ASCII padrão (fallback)
ASCII_TABLE = {i: chr(i) for i in range(0x20, 0x7F)}

# Palavras comuns para validação
VALID_WORDS = {
    'the', 'and', 'you', 'are', 'for', 'game', 'over', 'start', 'press',
    'player', 'score', 'level', 'life', 'lives', 'stage', 'continue',
    'select', 'zone', 'act', 'ring', 'world', 'round', 'bonus', 'time',
    'sega', 'developed', 'copyright', 'by', 'presented', 'end', 'the',
    'congratulations', 'try', 'again', 'credits', 'thank', 'play',
}


class UniversalMasterSystemExtractor:
    """
    Extrator universal para Master System.
    Detecta jogo por assinatura/CRC e usa tabela correta.
    """

    def __init__(self, caminho_rom=None):
        self.rom_path = None
        self.rom_data = None
        self.rom_size = 0
        self.rom_crc32 = None
        self.detected_game = None
        self.char_table = ASCII_TABLE
        self.terminator = 0x00
        self.tables = {'default': ASCII_TABLE}
        self.default_table_key = 'default'
        self.commands = {}
        self.text_regions = []
        self.filtered_texts = []

        if caminho_rom:
            self.carregar_rom(caminho_rom)


    @property
    def results(self):
        """Compat: some callers expect .results to exist."""
        return getattr(self, "filtered_texts", [])

    def carregar_rom(self, caminho_rom):
        """Carrega ROM e detecta jogo automaticamente."""
        self.rom_path = Path(caminho_rom)

        if not self.rom_path.exists():
            raise FileNotFoundError("ROM não encontrada")

        with open(self.rom_path, "rb") as f:
            self.rom_data = f.read()

        self.rom_size = len(self.rom_data)
        # Calcula CRC32 (full e sem header de 512 bytes)
        import zlib
        self.rom_crc32_full = format(zlib.crc32(self.rom_data) & 0xFFFFFFFF, '08X')
        self.rom_crc32_no512 = None
        if self.rom_size > 512:
            self.rom_crc32_no512 = format(zlib.crc32(self.rom_data[512:]) & 0xFFFFFFFF, '08X')

        # Mantém compatibilidade com código antigo
        self.rom_crc32 = self.rom_crc32_full
        self.rom_crc32_candidates = [c for c in [self.rom_crc32_full, self.rom_crc32_no512] if c]

        print(f"[OK] ROM: {self.rom_path.name}")
        print(f"[OK] Tamanho: {self.rom_size} bytes")
        if self.rom_crc32_no512:
            print(f"[OK] CRC32 (full): {self.rom_crc32_full} | (no512): {self.rom_crc32_no512}")
        else:
            print(f"[OK] CRC32: {self.rom_crc32_full}")

        # Detecta jogo
        self._detect_game()

    def _detect_game(self):
        """Detecta jogo por CRC32 ou assinatura."""
        # Primeiro tenta por CRC32 (mais preciso)
        for game_id, game_data in CHAR_TABLES.items():
            if any(c in game_data.get("crc32", []) for c in getattr(self, "rom_crc32_candidates", [self.rom_crc32])):
                self._load_game_profile(game_id, game_data)
                return

        # Se não encontrou, tenta por assinatura
        for game_id, game_data in CHAR_TABLES.items():
            for sig in game_data.get("signatures", []):
                offset = sig["offset"]
                expected = sig["bytes"]
                if offset + len(expected) <= self.rom_size:
                    if self.rom_data[offset:offset+len(expected)] == expected:
                        # Verifica se não é só o header TMR SEGA genérico
                        if expected != b"TMR SEGA":
                            self._load_game_profile(game_id, game_data)
                            return

        # Não encontrou - usa modo genérico
        print("[INFO] Jogo não reconhecido - usando modo ASCII + heurística")
        self.detected_game = "generic"
        self.char_table = ASCII_TABLE
        self.tables = {'default': ASCII_TABLE}
        self.default_table_key = 'default'
        self.terminator = 0x00

    def _load_game_profile(self, game_id, game_data):
        """Carrega perfil do jogo detectado."""
        self.detected_game = game_id

        # Suporta jogos com múltiplas tabelas (ex: Sonic, diferentes telas)
        self.tables = game_data.get("tables")
        if self.tables:
            default_key = game_data.get("default_table") or next(iter(self.tables.keys()))
            self.default_table_key = default_key
            self.char_table = self.tables.get(default_key, ASCII_TABLE)
        else:
            self.char_table = game_data.get("table", ASCII_TABLE)
            self.tables = {"default": self.char_table}
            self.default_table_key = "default"

        self.terminator = game_data.get("terminator", 0xFF)
        self.commands = game_data.get("commands", {})
        self.text_regions = game_data.get("text_regions", [])

        print(f"[OK] Jogo detectado: {game_data['name']}")
        if self.tables and len(self.tables) > 1:
            print(f"[OK] Tabelas carregadas: {list(self.tables.keys())} (default: {self.default_table_key})")
        print(f"[OK] Tabela ativa: {len(self.char_table)} chars")

    def _decode_text(self, data, char_table=None, terminator=None, commands=None, max_len=300):
        """Decodifica bytes usando tabela informada (ou a atual)."""
        char_table = char_table or self.char_table
        terminator = self.terminator if terminator is None else terminator
        commands = commands if commands is not None else self.commands

        result = []
        i = 0
        # Proteção contra blocos sem terminador / lixo
        hard_limit = min(len(data), max_len) if max_len else len(data)

        while i < hard_limit:
            byte = data[i]

            # Verifica terminador
            if terminator is not None and byte == terminator:
                break

            # Verifica comandos especiais
            if commands and byte in commands:
                extra = commands[byte]
                cmd_bytes = data[i:i+1+extra]
                result.append(f"[CMD:{cmd_bytes.hex().upper()}]")
                i += 1 + extra
                continue

            # Decodifica caractere
            if byte in char_table:
                result.append(char_table[byte])
            else:
                result.append(f"[{byte:02X}]")

            i += 1

        return ''.join(result)

    def _text_score(self, decoded):
        """Pontua uma string decodificada para escolher a melhor tabela."""
        clean = re.sub(r'\[[^\]]+\]', '', decoded).strip()
        if not clean:
            return 0

        letters = sum(1 for c in clean if c.isalpha())
        spaces = clean.count(' ')
        score = 0

        # Base
        score += min(len(clean), 40)
        score += letters * 2
        score += spaces

        # Penaliza lixo em excesso
        unknown = decoded.count('[')
        score -= unknown * 5

        # Bonus por palavras comuns
        words = re.findall(r'[a-zA-Z]+', clean.lower())
        for w in words:
            if w in VALID_WORDS:
                score += 20

        # Bonus por ter "vogais" (inclui Y, por causa de SKY / MY etc)
        if re.search(r'[aeiouyAEIOUY]', clean):
            score += 10
        else:
            score -= 30

        return score

    def _decode_best_table(self, block, table_keys, max_len=300):
        """Tenta várias tabelas e retorna a decodificação com melhor score."""
        best = None
        best_score = -10**9

        for key in table_keys:
            table = self.tables.get(key)
            if not table:
                continue
            decoded = self._decode_text(block, char_table=table, max_len=max_len)
            s = self._text_score(decoded)
            if s > best_score:
                best_score = s
                best = decoded

        # fallback: tabela ativa
        if best is None:
            best = self._decode_text(block, max_len=max_len)
        return best

    def _is_valid_text(self, text, min_len=3, min_letters=2):
        """Heurística simples para filtrar lixo."""
        clean = re.sub(r'\[[^\]]+\]', '', text).strip()
        if len(clean) < min_len:
            return False

        letters = sum(1 for c in clean if c.isalpha())
        if letters < min_letters:
            return False

        # Proporção de letras (evita strings cheias de símbolos)
        if letters / max(len(clean), 1) < 0.5:
            return False

        # Palavras comuns = quase certeza de texto real
        words = re.findall(r'[a-zA-Z]+', clean.lower())
        if any(w in VALID_WORDS for w in words):
            return True

        # Frase com espaço tende a ser texto
        if ' ' in clean and letters >= 5:
            return True

        # Vogais (inclui Y para palavras tipo SKY)
        if not re.search(r'[aeiouyAEIOUY]', clean):
            return False

        return len(clean) >= min_len

    def _extract_from_regions(self):
        """Extrai texto de regiões conhecidas."""
        texts = []

        for region in self.text_regions:
            start = region['start']
            end = region['end']
            name = region['name']
            skip = int(region.get('skip', 0))
            table_keys = region.get('tables') or [getattr(self, 'default_table_key', 'default')]
            max_len = region.get('max_len', 300)

            if end > self.rom_size:
                continue

            data = self.rom_data[start:end]

            # Divide por terminador
            blocks = []
            current = []
            block_start = start

            for i, byte in enumerate(data):
                if byte == self.terminator:
                    if current:
                        blocks.append((block_start, bytes(current)))
                    current = []
                    block_start = start + i + 1
                else:
                    current.append(byte)

            # Decodifica
            for offset, block in blocks:
                if len(block) >= 1:
                    prefix = block[:skip] if skip else b''
                    payload = block[skip:] if skip else block

                    decoded = self._decode_best_table(payload, table_keys=table_keys, max_len=max_len)
                    clean = re.sub(r'\[[^\]]+\]', '', decoded).strip()

                    # Regiões conhecidas podem ter strings menores (ex: "SEGA")
                    if self._is_valid_text(decoded, min_len=2, min_letters=1):
                        texts.append({
                            'offset': offset + skip,
                            'raw': payload.hex().upper(),
                            'decoded': decoded,
                            'clean': clean,
                            'region': name,
                            'prefix_hex': prefix.hex().upper() if prefix else ''
                        })

        return texts

    def _extract_by_terminator_scan(self):
        """Busca textos terminados pelo terminador em toda ROM."""
        texts = []
        min_valid_byte = min(self.char_table.keys()) if self.char_table else 0x00
        max_valid_byte = max(self.char_table.keys()) if self.char_table else 0x7F

        i = 0
        while i < self.rom_size - 3:
            # Verifica se byte está na tabela
            if self.rom_data[i] in self.char_table:
                start = i
                length = 0
                valid = True

                while i < self.rom_size and length < 300:
                    byte = self.rom_data[i]

                    if byte == self.terminator:
                        # Encontrou terminador
                        if length >= 3:
                            block = self.rom_data[start:i]
                            decoded = self._decode_text(block)

                            if self._is_valid_text(decoded):
                                clean = re.sub(r'\[[^\]]+\]', '', decoded).strip()
                                texts.append({
                                    'offset': start,
                                    'decoded': decoded,
                                    'clean': clean,
                                    'region': 'Scan'
                                })
                        break
                    elif byte in self.char_table or byte in self.commands:
                        length += 1
                        i += 1
                    else:
                        valid = False
                        break

                if not valid:
                    i = start + 1
                    continue

            i += 1

        return texts

    def _extract_ascii(self):
        """Extrai textos ASCII puros."""
        texts = []
        buffer = bytearray()
        start = None

        for i, b in enumerate(self.rom_data):
            if 0x20 <= b <= 0x7E:
                if start is None:
                    start = i
                buffer.append(b)
            else:
                if start is not None and len(buffer) >= 5:
                    text = buffer.decode('ascii', errors='replace').strip()
                    if self._is_valid_text(text):
                        texts.append({
                            'offset': start,
                            'decoded': text,
                            'clean': text,
                            'region': 'ASCII'
                        })
                buffer = bytearray()
                start = None

        return texts

    def extract_all(self):
        """Extrai todos os textos."""
        if self.rom_data is None:
            raise RuntimeError("Nenhuma ROM carregada")

        self.filtered_texts = []
        seen_offsets = set()

        # 1. Regiões conhecidas (se houver)
        if self.text_regions:
            region_texts = self._extract_from_regions()
            for t in region_texts:
                if t['offset'] not in seen_offsets:
                    self.filtered_texts.append(t)
                    seen_offsets.add(t['offset'])
            print(f"[OK] Regiões conhecidas: {len(region_texts)} textos")

        # 2. Scan por terminador (se não for genérico)
        if self.detected_game != "generic":
            scan_texts = self._extract_by_terminator_scan()
            for t in scan_texts:
                if t['offset'] not in seen_offsets:
                    self.filtered_texts.append(t)
                    seen_offsets.add(t['offset'])
            print(f"[OK] Scan por terminador: {len(scan_texts)} textos")

        # 3. ASCII (sempre)
        ascii_texts = self._extract_ascii()
        for t in ascii_texts:
            if t['offset'] not in seen_offsets:
                self.filtered_texts.append(t)
                seen_offsets.add(t['offset'])
        print(f"[OK] ASCII: {len(ascii_texts)} textos")

        # Ordena por offset
        self.filtered_texts.sort(key=lambda x: x['offset'])

        print(f"[OK] TOTAL: {len(self.filtered_texts)} textos extraídos")
        return len(self.filtered_texts)


    def save_results(self, output_dir=None):
        """Salva arquivos de saída na pasta da ROM (ou output_dir).

        Saídas:
          - *_clean_blocks.txt  -> arquivo principal para tradução (blocos legíveis)
          - *_mapping.json      -> metadados para reinserção (offsets/limites)
          - *_extracted.txt     -> dump completo (debug)
          - *_extracted.json    -> dump estruturado (debug)

        Retorna o caminho do *_clean_blocks.txt.
        """
        if output_dir is None:
            output_dir = Path(self.rom_path).parent
        else:
            output_dir = Path(output_dir)

        rom_name = Path(self.rom_path).name
        base_name = rom_name.replace('.sms', '').replace('.SMS', '')

        clean_blocks_path = output_dir / f"{base_name}_clean_blocks.txt"
        mapping_path = output_dir / f"{base_name}_mapping.json"
        extracted_txt_path = output_dir / f"{base_name}_extracted.txt"
        extracted_json_path = output_dir / f"{base_name}_extracted.json"

        # Principal (tradução)
        self._save_clean_blocks(clean_blocks_path)
        # Principal (reinserção)
        self._save_mapping(mapping_path, clean_blocks_path.name)

        # Debug
        self._save_extracted_txt(extracted_txt_path)
        self._save_json(extracted_json_path)

        return str(clean_blocks_path)

    def _save_extracted_txt(self, txt_path: Path):
        """Dump completo (com offsets) — útil para depurar."""
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# NeuroROM AI - Master System Text Extraction\n")
            f.write(f"# ROM: {Path(self.rom_path).name}\n")
            f.write(f"# Total: {len(self.results)} textos\n")
            f.write("#" + "=" * 70 + "\n\n")

            for i, text_data in enumerate(self.results, 1):
                f.write(f"[{i:04d}] @{text_data['offset']:06X} ({text_data.get('region', 'Unknown')})\n")
                f.write(text_data['clean'] + "\n")
                f.write("-" * 50 + "\n\n")

    def _save_clean_blocks(self, clean_path: Path):
        """Arquivo pensado para IA traduzir: blocos legíveis e estáveis."""
        with open(clean_path, 'w', encoding='utf-8') as f:
            f.write("# NeuroROM AI - Master System CLEAN BLOCKS\n")
            f.write(f"# ROM: {Path(self.rom_path).name}\n")
            f.write(f"# Total: {len(self.results)} blocos\n")
            f.write("#" + "=" * 70 + "\n\n")

            for i, t in enumerate(self.results, 1):
                region = t.get('region', 'Unknown')
                # Cabeçalho do bloco: não traduzir
                f.write(f"[BLOCK {i:04d}] @{t['offset']:06X} ({region})\n")
                # Conteúdo: traduzir
                f.write(t['clean'].rstrip() + "\n")
                f.write("\n")

    def _save_mapping(self, mapping_path: Path, clean_blocks_filename: str):
        """Gera mapping para reinserção (1:1 com a ordem dos blocos)."""
        import json

        entries = []
        for i, t in enumerate(self.results, 1):
            decoded = (t.get('decoded') or t.get('clean') or '')
            # Limite conservador: bytes ~= chars para ASCII; para tabelas custom, ainda ajuda.
            max_bytes = max(1, len(decoded))
            entries.append({
                'id': i,
                'offset': int(t['offset']),
                'region': t.get('region', 'Unknown'),
                'max_bytes': int(max_bytes),
            })

        payload = {
            'rom_filename': Path(self.rom_path).name,
            'rom_path': str(Path(self.rom_path)),
            'crc32_full': self.calculate_crc32(),
            'game_id': self.detected_game,
            'terminator': int(self.terminator),
            'clean_blocks_file': clean_blocks_filename,
            'entries': entries,
        }

        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def add_game_table(game_id, name, table, terminator=0xFF, crc32_list=None):
        """
        Permite adicionar novas tabelas em runtime.

        Exemplo:
            extractor.add_game_table(
                "my_game",
                "My Game Name",
                {0x00: ' ', 0x01: 'A', ...},
                terminator=0xFF,
                crc32_list=["ABCD1234"]
            )
        """
        CHAR_TABLES[game_id] = {
            "name": name,
            "signatures": [],
            "crc32": crc32_list or [],
            "table": table,
            "terminator": terminator,
            "commands": {},
            "text_regions": []
        }
        print(f"[OK] Tabela '{name}' adicionada ao banco de dados")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python MASTER_SYSTEM_UNIVERSAL_EXTRACTOR.py <rom.sms>")
        print("\nJogos com tabelas cadastradas:")
        for gid, gdata in CHAR_TABLES.items():
            print(f"  - {gdata['name']}")
        sys.exit(1)

    extractor = UniversalMasterSystemExtractor(sys.argv[1])
    total = extractor.extract_all()

    if total > 0:
        output = extractor.save_results()
        print(f"\nArquivo salvo: {output}")
    else:
        print("\nNenhum texto encontrado.")
