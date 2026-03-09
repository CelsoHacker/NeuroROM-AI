# -*- coding: utf-8 -*-
"""
TBL LOADER - Carregador de Tabelas Customizadas
================================================
Baseado nas técnicas clássicas de romhacking brasileiro.

Referências:
- Livro Branco do Romhacking (Fserve/Tradu-Roms)
- Tutoriais da comunidade PO.B.R.E

Autor: Sistema V5
Data: 2026-01
"""

from pathlib import Path
from typing import Dict, Optional
import re


class TBLLoader:
    """
    Carregador de tabelas .tbl (formato padrão de romhacking).

    Formato TBL:
    HEX=CHAR          (1 byte:  00=0, 0A=A, FF= )
    HHHH=CHAR          (2 bytes: 9209=A, 8809=O)
    HHHHHH=CHAR        (3 bytes, se necessário)

    Multi-byte é padrão em romhacking: hex com 4+ dígitos = 2+ bytes.
    """

    def __init__(self, tbl_path: Optional[str] = None):
        self.char_map: Dict[int, str] = {}          # byte_value -> char (1-byte)
        self.multi_byte_map: Dict[bytes, str] = {}   # byte_seq -> char (multi-byte)
        self.max_entry_len: int = 1                   # Maior sequência no mapa
        self.reverse_map: Dict[str, bytes] = {}       # char -> byte_seq (para encode)

        if tbl_path:
            self.load_tbl(tbl_path)

    def load_tbl(self, tbl_path: str):
        """
        Carrega arquivo .tbl no formato HEX=CHAR.

        Formato aceito:
        - Linhas vazias são ignoradas
        - Linhas começando com # são comentários
        - Formato: HEXVALUE=CHARACTER (HH=1byte, HHHH=2bytes, etc.)
        """
        print(f"Carregando tabela: {Path(tbl_path).name}")

        with open(tbl_path, 'r', encoding='utf-8') as f:
            line_num = 0
            for line in f:
                line_num += 1
                # Strip only newline/carriage-return, preserve spaces in char value
                line = line.rstrip('\n\r')
                check = line.strip()

                # Ignora vazias e comentários
                if not check or check.startswith('#'):
                    continue

                # Processa linha
                if '=' in line:
                    try:
                        hex_val, char = line.split('=', 1)
                        hex_val = hex_val.strip()
                        # Keep char as-is: empty string = end-of-line marker,
                        # single space = space character (standard TBL convention)

                        # Determina tamanho da entrada (2 hex digits = 1 byte)
                        byte_len = (len(hex_val) + 1) // 2
                        byte_value = int(hex_val, 16)

                        if byte_len == 1:
                            # Entrada de 1 byte (formato clássico)
                            self.char_map[byte_value] = char
                        else:
                            # Entrada multi-byte (2+ bytes)
                            byte_seq = byte_value.to_bytes(byte_len, 'big')
                            self.multi_byte_map[byte_seq] = char
                            if byte_len > self.max_entry_len:
                                self.max_entry_len = byte_len

                        # Mapa reverso para encode
                        byte_seq_r = byte_value.to_bytes(byte_len, 'big')
                        self.reverse_map[char] = byte_seq_r

                    except ValueError:
                        print(f"Linha {line_num} invalida: {line}")
                        continue

        total = len(self.char_map) + len(self.multi_byte_map)
        print(f"{total} caracteres mapeados (max_entry_len={self.max_entry_len})\n")

    def decode_bytes(self, data: bytes, max_length: int = 200) -> str:
        """
        Decodifica sequência de bytes usando tabela.
        Suporta entradas multi-byte (tenta match mais longo primeiro).

        Args:
            data: Bytes para decodificar
            max_length: Tamanho máximo de caracteres na string resultado

        Returns:
            String decodificada
        """
        result = []
        i = 0
        data_len = len(data)

        while i < data_len and len(result) < max_length:
            # Terminadores comuns (só checa primeiro byte)
            if data[i] in (0x00, 0xFF):
                break

            matched = False

            # Tenta match mais longo primeiro (multi-byte)
            for entry_len in range(min(self.max_entry_len, data_len - i), 1, -1):
                seq = data[i:i + entry_len]
                if seq in self.multi_byte_map:
                    result.append(self.multi_byte_map[seq])
                    i += entry_len
                    matched = True
                    break

            if matched:
                continue

            # Fallback: match de 1 byte
            if data[i] in self.char_map:
                result.append(self.char_map[data[i]])
                i += 1
            else:
                # Byte desconhecido - para aqui
                break

        return ''.join(result)

    def encode_text(self, text: str) -> Optional[bytes]:
        """
        Codifica texto de volta para bytes usando mapa reverso.

        Args:
            text: String para codificar

        Returns:
            Bytes codificados ou None se algum char não tem mapeamento
        """
        result = bytearray()
        for ch in text:
            if ch in self.reverse_map:
                result.extend(self.reverse_map[ch])
            else:
                return None
        return bytes(result)

    def merge_entries(self, new_entries: Dict[int, str]):
        """
        Integra novos mapeamentos (ex: caracteres acentuados do Font Editor).

        Args:
            new_entries: Dict[byte_value, char] para adicionar/sobrescrever
        """
        for byte_val, char in new_entries.items():
            self.char_map[byte_val] = char
            byte_seq = byte_val.to_bytes(1, 'big')
            self.reverse_map[char] = byte_seq

    def build_default_table(self) -> Dict[int, str]:
        """
        Constrói tabela padrão baseada em heurísticas.

        Retorna tabela genérica para ROMs sem .tbl disponível.
        """
        table = {}

        # Método 1: ASCII padrão (comum em PC games)
        for i in range(0x20, 0x7F):
            table[i] = chr(i)

        # Terminadores
        table[0x00] = '\n'
        table[0xFF] = '\n'
        table[0xFE] = ' '

        return table

    def build_console_table(self, console_type: str = 'nes') -> Dict[int, str]:
        """
        Tabela típica para consoles clássicos.

        Args:
            console_type: 'nes', 'snes', 'genesis'
        """
        table = {}

        if console_type in ['nes', 'snes']:
            # Números 0-9 (valores 00-09)
            for i in range(10):
                table[i] = str(i)

            # Letras A-Z (valores 0A-23)
            for i in range(26):
                table[0x0A + i] = chr(0x41 + i)

            # Letras a-z (valores 24-3D)
            for i in range(26):
                table[0x24 + i] = chr(0x61 + i)

            # Símbolos comuns
            table[0xFF] = ' '   # Espaço
            table[0x40] = '!'
            table[0x41] = '?'
            table[0x42] = '.'
            table[0x43] = ','
            table[0x44] = '-'
            table[0x45] = '"'
            table[0x00] = '\n'  # Fim de string

        elif console_type == 'genesis':
            # Genesis usa tabelas variadas
            # Fallback para ASCII
            for i in range(0x20, 0x7F):
                table[i] = chr(i)

        return table

    def auto_detect_table(self, rom_data: bytes) -> Dict[int, str]:
        """
        Detecta automaticamente tipo de tabela procurando padrões ASCII.

        Técnica do "Livro Branco do Romhacking":
        1. Procura palavras comuns em ASCII
        2. Se achar, usa tabela ASCII
        3. Se não achar, assume tabela de console
        """
        print("🔍 Detectando tipo de tabela...")

        # Palavras comuns que aparecem em jogos
        common_words = [
            b'START',
            b'GAME',
            b'PLAYER',
            b'PRESS',
            b'CONTINUE',
            b'LEVEL',
            b'SCORE',
            b'TIME',
            b'PAUSE',
            b'OPTIONS',
        ]

        # Procura por ASCII
        ascii_found = False
        for word in common_words:
            if word in rom_data:
                ascii_found = True
                print(f"✅ ASCII detectado (palavra: {word.decode('ascii')})")
                break

        if ascii_found:
            print("📋 Usando tabela ASCII padrão")
            return self.build_default_table()
        else:
            print("📋 Usando tabela de console (NES/SNES)")
            return self.build_console_table('snes')


def create_sample_table(output_path: str, console_type: str = 'snes'):
    """
    Cria arquivo .tbl de exemplo.

    Args:
        output_path: Caminho para salvar .tbl
        console_type: Tipo de console ('nes', 'snes', 'genesis')
    """
    loader = TBLLoader()
    table = loader.build_console_table(console_type)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Tabela de caracteres - {console_type.upper()}\n")
        f.write("# Formato: HEX=CHAR\n")
        f.write("# Gerado automaticamente\n\n")

        # Ordena por valor hex
        for byte_val in sorted(table.keys()):
            char = table[byte_val]
            # Escape especial para newline
            if char == '\n':
                char = '\\n'
            f.write(f"{byte_val:02X}={char}\n")

    print(f"✅ Tabela salva: {output_path}")


if __name__ == '__main__':
    # Teste
    import sys

    if len(sys.argv) > 1:
        # Carrega tabela
        loader = TBLLoader(sys.argv[1])
        print(f"Tabela carregada: {len(loader.char_map)} caracteres")
    else:
        # Cria tabela de exemplo
        create_sample_table('exemplo_snes.tbl', 'snes')
