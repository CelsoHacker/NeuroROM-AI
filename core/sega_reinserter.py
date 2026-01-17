#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sega Reinserter - Master System & Mega Drive/Genesis
=====================================================
Reinsertor simples e direto para plataformas Sega.

Funciona com arquivos TXT no formato:
[0xOFFSET] texto original
[0xOFFSET] texto traduzido

Características:
- ASCII direto (0x20-0x7E)
- Padding automático com 0x00
- Backup automático
- Validação de tamanho

Author: NeuroROM AI
License: MIT
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class SegaReinserter:
    """Reinsertor simples para plataformas Sega (Master System, Mega Drive)"""

    def __init__(self, rom_path: str):
        """
        Inicializa reinsertor Sega

        Args:
            rom_path: Caminho da ROM original
        """
        self.rom_path = Path(rom_path)

        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM não encontrada: {rom_path}")

        # Carrega ROM
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        self.original_size = len(self.rom_data)

        # Stats
        self.stats = {
            'total': 0,
            'inserted': 0,
            'skipped': 0,
            'truncated': 0,
            'errors': []
        }

    def load_translations(self, translation_file: str) -> List[Dict]:
        """
        Carrega arquivo de traduções no formato:
        [0xOFFSET] texto traduzido

        Args:
            translation_file: Caminho do arquivo de traduções

        Returns:
            Lista de dicts com offset e texto
        """
        translations = []

        with open(translation_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # Ignora comentários e linhas vazias
                if not line or line.startswith('#'):
                    continue

                # Parse formato [0xOFFSET] texto
                if line.startswith('[0x') and ']' in line:
                    try:
                        # Extrai offset
                        offset_end = line.index(']')
                        offset_hex = line[1:offset_end]
                        offset = int(offset_hex, 16)

                        # Extrai texto
                        text = line[offset_end + 1:].strip()

                        if text:
                            translations.append({
                                'offset': offset,
                                'text': text
                            })
                    except (ValueError, IndexError):
                        continue

        return translations

    def reinsert(self, translations: List[Dict], output_path: Optional[str] = None,
                 create_backup: bool = True) -> Tuple[bool, str]:
        """
        Reinsere textos traduzidos na ROM

        Args:
            translations: Lista de traduções [{offset, text}]
            output_path: Caminho de saída (opcional)
            create_backup: Se True, cria backup

        Returns:
            (sucesso, mensagem)
        """
        if output_path is None:
            output_path = self.rom_path.parent / f"{self.rom_path.stem}_translated{self.rom_path.suffix}"
        else:
            output_path = Path(output_path)

        # Backup
        if create_backup:
            backup_path = self.rom_path.parent / f"{self.rom_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{self.rom_path.suffix}"
            shutil.copy2(self.rom_path, backup_path)
            print(f"✅ Backup criado: {backup_path.name}")

        self.stats['total'] = len(translations)

        print(f"\n{'='*70}")
        print(f"🔄 SEGA REINSERTER - Reinserção de Textos")
        print(f"{'='*70}")
        print(f"📂 ROM: {self.rom_path.name}")
        print(f"📊 Textos a inserir: {len(translations)}")
        print(f"{'='*70}\n")

        # Processa cada tradução
        for item in translations:
            offset = item['offset']
            text = item['text']

            try:
                self._insert_text(offset, text)
                self.stats['inserted'] += 1
            except Exception as e:
                self.stats['errors'].append({
                    'offset': offset,
                    'error': str(e)
                })
                self.stats['skipped'] += 1

        # Salva ROM modificada
        with open(output_path, 'wb') as f:
            f.write(self.rom_data)

        # Relatório
        success = self.stats['inserted'] > 0

        print(f"\n{'='*70}")
        print(f"📊 RESULTADO DA REINSERÇÃO")
        print(f"{'='*70}")
        print(f"✅ Inseridos: {self.stats['inserted']}")
        print(f"⚠️  Truncados: {self.stats['truncated']}")
        print(f"❌ Ignorados: {self.stats['skipped']}")
        print(f"📂 Saída: {output_path.name}")
        print(f"{'='*70}\n")

        if self.stats['errors']:
            print("❌ ERROS:")
            for err in self.stats['errors'][:5]:  # Mostra só 5 primeiros
                print(f"   [0x{err['offset']:X}] {err['error']}")

        message = f"Reinserção concluída! {self.stats['inserted']}/{self.stats['total']} textos inseridos."
        return success, message

    def _insert_text(self, offset: int, text: str):
        """
        Insere um texto no offset especificado

        Args:
            offset: Offset na ROM
            text: Texto a inserir
        """
        # Valida offset
        if offset < 0 or offset >= len(self.rom_data):
            raise ValueError(f"Offset inválido: 0x{offset:X}")

        # Codifica texto para ASCII
        try:
            encoded = text.encode('ascii', errors='replace')
        except Exception:
            # Fallback: remove caracteres não-ASCII
            encoded = bytes([b if 0x20 <= b <= 0x7E else ord('?') for b in text.encode('utf-8', errors='ignore')])

        # Encontra tamanho original (até próximo terminador)
        original_end = offset
        while original_end < len(self.rom_data) and self.rom_data[original_end] not in [0x00, 0xFF]:
            original_end += 1

        original_length = original_end - offset

        # Se texto traduzido é maior, trunca
        if len(encoded) > original_length:
            encoded = encoded[:original_length]
            self.stats['truncated'] += 1

        # Escreve texto
        for i, byte in enumerate(encoded):
            self.rom_data[offset + i] = byte

        # Preenche resto com terminador
        for i in range(len(encoded), original_length):
            self.rom_data[offset + i] = 0x00


def reinsert_sega_rom(rom_path: str, translation_file: str,
                       output_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Função de conveniência para reinserção Sega

    Args:
        rom_path: ROM original
        translation_file: Arquivo com traduções
        output_path: ROM de saída (opcional)

    Returns:
        (sucesso, mensagem)
    """
    reinserter = SegaReinserter(rom_path)
    translations = reinserter.load_translations(translation_file)

    if not translations:
        return False, "Nenhuma tradução encontrada no arquivo"

    return reinserter.reinsert(translations, output_path)


def main():
    """CLI Interface"""
    import sys

    print("="*70)
    print("  NeuroROM AI - Sega Text Reinserter")
    print("  Master System + Mega Drive/Genesis")
    print("="*70)
    print()

    if len(sys.argv) < 3:
        print("Uso:")
        print(f"  python {Path(__file__).name} <rom_file> <translation_file> [output.rom]")
        print()
        print("Exemplos:")
        print(f"  python {Path(__file__).name} alex_kidd.sms alex_kidd_translated.txt")
        print(f"  python {Path(__file__).name} sonic.gen sonic_ptbr.txt sonic_ptbr.gen")
        print()
        print("Formato do arquivo de tradução:")
        print("  [0x1234] Texto traduzido aqui")
        print("  [0x5678] Outro texto traduzido")
        print()
        sys.exit(1)

    rom_path = sys.argv[1]
    translation_file = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        success, message = reinsert_sega_rom(rom_path, translation_file, output_path)
        print(f"\n{'✅' if success else '❌'} {message}")
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
