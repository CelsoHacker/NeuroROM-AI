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
    HEX=CHAR

    Exemplo:
    00=0
    0A=A
    24=a
    FF=
    """

    def __init__(self, tbl_path: Optional[str] = None):
        self.char_map: Dict[int, str] = {}

        if tbl_path:
            self.load_tbl(tbl_path)

    def load_tbl(self, tbl_path: str):
        """
        Carrega arquivo .tbl no formato HEX=CHAR.

        Formato aceito:
        - Linhas vazias são ignoradas
        - Linhas começando com # são comentários
        - Formato: HEXVALUE=CHARACTER
        """
        print(f"📂 Carregando tabela: {Path(tbl_path).name}")

        with open(tbl_path, 'r', encoding='utf-8') as f:
            line_num = 0
            for line in f:
                line_num += 1
                line = line.strip()

                # Ignora vazias e comentários
                if not line or line.startswith('#'):
                    continue

                # Processa linha
                if '=' in line:
                    try:
                        hex_val, char = line.split('=', 1)
                        hex_val = hex_val.strip()

                        # Converte hex para int
                        byte_value = int(hex_val, 16)

                        # Armazena mapeamento
                        self.char_map[byte_value] = char

                    except ValueError as e:
                        print(f"⚠️  Linha {line_num} inválida: {line}")
                        continue

        print(f"✅ {len(self.char_map)} caracteres mapeados\n")

    def decode_bytes(self, data: bytes, max_length: int = 200) -> str:
        """
        Decodifica sequência de bytes usando tabela.

        Args:
            data: Bytes para decodificar
            max_length: Tamanho máximo da string

        Returns:
            String decodificada
        """
        result = []

        for i, byte in enumerate(data):
            if i >= max_length:
                break

            # Terminadores comuns
            if byte in [0x00, 0xFF]:
                break

            # Mapeia byte
            if byte in self.char_map:
                result.append(self.char_map[byte])
            else:
                # Byte desconhecido - para aqui
                break

        return ''.join(result)

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
