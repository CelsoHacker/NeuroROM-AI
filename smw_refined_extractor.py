#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUPER MARIO WORLD - EXTRATOR REFINADO COM FILTROS AGRESSIVOS
=============================================================

Versão 2: Filtros ultra-rigorosos para eliminar 90% de lixo
Meta: 200-500 textos VÁLIDOS (não 7,601 textos com 90% lixo)
"""

import re
from pathlib import Path
from typing import List, Tuple
from collections import Counter


class AggressiveTextFilter:
    """Filtros ultra-rigorosos para eliminar lixo binário"""

    @staticmethod
    def is_repetitive_pattern(text: str) -> bool:
        """
        FILTRO 1: Detecta padrões repetitivos
        Exemplos rejeitados: AAAAA, BBBBB, ABABABAB, 123123123
        """
        text_clean = text.replace(' ', '').replace('-', '').replace(',', '')

        if len(text_clean) < 4:
            return False

        # Detecta repetição de caractere único (AAAAA)
        if len(set(text_clean)) == 1:
            return True

        # Detecta padrões de 2-4 chars repetidos
        for pattern_len in [2, 3, 4]:
            if len(text_clean) >= pattern_len * 3:
                # Pega primeiros N chars como padrão
                pattern = text_clean[:pattern_len]
                # Verifica se texto inteiro é repetição desse padrão
                expected = pattern * (len(text_clean) // pattern_len + 1)
                if text_clean in expected[:len(text_clean)]:
                    return True

        return False

    @staticmethod
    def is_binary_sequence(text: str) -> bool:
        """
        FILTRO 2: Detecta sequências binárias/hex
        Exemplos: "0123456789ABCDEF", "00 01 02 03"
        """
        text_clean = text.replace(' ', '').upper()

        # Sequência alfabética ascendente/descendente > 5 chars
        for i in range(len(text_clean) - 5):
            is_ascending = all(
                ord(text_clean[i + j + 1]) == ord(text_clean[i + j]) + 1
                for j in range(5)
            )
            is_descending = all(
                ord(text_clean[i + j + 1]) == ord(text_clean[i + j]) - 1
                for j in range(5)
            )
            if is_ascending or is_descending:
                return True

        return False

    @staticmethod
    def has_sufficient_diversity(text: str) -> bool:
        """
        FILTRO 3: Exige diversidade de caracteres
        Regra: Textos >10 chars devem ter pelo menos 4 caracteres únicos
        """
        text_clean = text.replace(' ', '')

        if len(text_clean) <= 10:
            return True  # Textos curtos não precisam diversidade

        unique_chars = len(set(text_clean))
        diversity_ratio = unique_chars / len(text_clean)

        # Pelo menos 30% de diversidade OU 4+ caracteres únicos
        return diversity_ratio >= 0.3 or unique_chars >= 4

    @staticmethod
    def has_valid_text_structure(text: str) -> bool:
        """
        FILTRO 4: Valida estrutura de texto real
        Requisitos:
        - Pelo menos 50% caracteres alfabéticos
        - Pelo menos 2 vogais
        - Não pode ser só maiúsculas/minúsculas/números
        """
        if len(text) < 4:
            return False

        # Pelo menos 50% alfabético
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.5:
            return False

        # Pelo menos 2 vogais
        vowels = set('AEIOUaeiou')
        vowel_count = sum(1 for c in text if c in vowels)
        if vowel_count < 2:
            return False

        # Não pode ser só números
        if text.replace(' ', '').isdigit():
            return False

        return True

    @staticmethod
    def is_numeric_sequence(text: str) -> bool:
        """
        FILTRO 5: Remove sequências numéricas puras
        Exemplos: "123456", "0 1 2 3 4"
        """
        text_clean = text.replace(' ', '').replace('-', '').replace(',', '')
        return text_clean.isdigit() and len(text_clean) >= 3

    @staticmethod
    def has_too_many_special_chars(text: str) -> bool:
        """
        FILTRO 6: Filtra textos com >30% caracteres não-alfanuméricos
        """
        if len(text) < 4:
            return False

        special_count = sum(1 for c in text if not c.isalnum() and c != ' ')
        ratio = special_count / len(text)

        return ratio > 0.3

    @staticmethod
    def is_valid_game_text(text: str) -> bool:
        """
        VALIDAÇÃO MASTER: Aplica TODOS os filtros

        Returns:
            True se texto é válido (PASSA em todos os filtros)
        """
        # REJEITA se for qualquer um destes:
        if AggressiveTextFilter.is_repetitive_pattern(text):
            return False

        if AggressiveTextFilter.is_binary_sequence(text):
            return False

        if not AggressiveTextFilter.has_sufficient_diversity(text):
            return False

        if not AggressiveTextFilter.has_valid_text_structure(text):
            return False

        if AggressiveTextFilter.is_numeric_sequence(text):
            return False

        if AggressiveTextFilter.has_too_many_special_chars(text):
            return False

        return True


class SMWRefinedExtractor:
    """Extrator refinado com filtros ultra-rigorosos"""

    def __init__(self, raw_texts_file: str):
        self.raw_texts_file = Path(raw_texts_file)
        self.filtered_texts = []
        self.stats = {
            'total_input': 0,
            'filtered_out': {},
            'valid_output': 0
        }

    def load_and_filter(self) -> List[str]:
        """Carrega textos brutos e aplica filtros agressivos"""
        print("=" * 80)
        print("🧹 REFINAMENTO COM FILTROS AGRESSIVOS")
        print("=" * 80)

        # Carrega textos brutos
        print(f"\n📂 Carregando: {self.raw_texts_file.name}")
        with open(self.raw_texts_file, 'r', encoding='utf-8') as f:
            raw_texts = [line.strip() for line in f if line.strip()]

        self.stats['total_input'] = len(raw_texts)
        print(f"✅ {len(raw_texts):,} textos carregados")

        # Aplica filtros
        print("\n🔍 Aplicando 6 filtros agressivos...")
        valid_texts = []

        for text in raw_texts:
            if AggressiveTextFilter.is_valid_game_text(text):
                valid_texts.append(text)

        self.stats['valid_output'] = len(valid_texts)
        self.stats['filtered_out']['total'] = len(raw_texts) - len(valid_texts)

        # Remove duplicatas
        valid_texts = list(dict.fromkeys(valid_texts))
        self.filtered_texts = valid_texts

        return valid_texts

    def apply_smw_keyword_boost(self) -> List[str]:
        """
        BOOST: Prioriza textos com palavras conhecidas do SMW
        """
        print("\n🎮 Aplicando boost de palavras-chave do SMW...")

        smw_keywords = {
            'MARIO', 'LUIGI', 'YOSHI', 'BOWSER', 'PEACH',
            'WORLD', 'STAR', 'COIN', 'POWER', 'FIRE',
            'CASTLE', 'GHOST', 'HOUSE', 'BONUS', 'TIME',
            'GAME', 'OVER', 'START', 'CONTINUE', 'PLAYER',
            'LIVES', 'SCORE', 'LEVEL'
        }

        boosted = []
        regular = []

        for text in self.filtered_texts:
            text_upper = text.upper()
            has_keyword = any(kw in text_upper for kw in smw_keywords)

            if has_keyword:
                boosted.append(text)
            else:
                regular.append(text)

        print(f"   ⭐ {len(boosted)} textos com palavras-chave")
        print(f"   📝 {len(regular)} textos regulares")

        # Retorna boosted primeiro
        return boosted + regular

    def save_filtered(self, output_path: str):
        """Salva textos filtrados"""
        output_file = Path(output_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            for text in self.filtered_texts:
                f.write(f"{text}\n")

        print(f"\n💾 {len(self.filtered_texts):,} textos válidos salvos em:")
        print(f"   {output_file.name}")

    def print_stats(self):
        """Mostra estatísticas"""
        print("\n" + "=" * 80)
        print("📊 ESTATÍSTICAS DE FILTRAGEM")
        print("=" * 80)
        print(f"Entrada total:     {self.stats['total_input']:,} textos")
        print(f"Filtrados (lixo):  {self.stats['filtered_out']['total']:,} textos")
        print(f"Válidos (output):  {self.stats['valid_output']:,} textos")

        if self.stats['total_input'] > 0:
            cleanup_rate = (self.stats['filtered_out']['total'] / self.stats['total_input']) * 100
            print(f"Taxa de limpeza:   {cleanup_rate:.1f}%")

        print("=" * 80)

    def print_preview(self, limit: int = 50):
        """Mostra preview dos textos válidos"""
        print("\n" + "=" * 80)
        print(f"📝 PREVIEW DOS PRIMEIROS {limit} TEXTOS VÁLIDOS:")
        print("=" * 80)

        for i, text in enumerate(self.filtered_texts[:limit], 1):
            print(f"{i:3d}. {text}")

        if len(self.filtered_texts) > limit:
            print(f"\n... e mais {len(self.filtered_texts) - limit} textos")


def main():
    """Função principal"""

    # Arquivo de entrada (gerado pelo extrator agressivo)
    input_file = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World_FULL_EXTRACTION.txt"

    # Verifica se existe
    if not Path(input_file).exists():
        print(f"❌ Arquivo não encontrado: {input_file}")
        print("\n💡 Execute 'smw_aggressive_extractor.py' primeiro!")
        return

    # Cria refinador
    refiner = SMWRefinedExtractor(input_file)

    # Executa filtragem
    valid_texts = refiner.load_and_filter()

    # Aplica boost de palavras-chave
    refiner.filtered_texts = refiner.apply_smw_keyword_boost()

    # Preview
    refiner.print_preview(limit=50)

    # Estatísticas
    refiner.print_stats()

    # Salva resultado
    output_path = input_file.replace('_FULL_EXTRACTION.txt', '_REFINED.txt')
    refiner.save_filtered(output_path)

    # Avaliação final
    print("\n" + "=" * 80)
    print("✅ AVALIAÇÃO FINAL:")
    print("=" * 80)

    valid_count = len(refiner.filtered_texts)

    if valid_count >= 200:
        print(f"🎉 EXCELENTE! {valid_count} textos válidos (meta 200+ atingida)")
    elif valid_count >= 100:
        print(f"✅ BOM! {valid_count} textos (perto da meta)")
    elif valid_count >= 50:
        print(f"⚠️  REGULAR. {valid_count} textos (ajustar filtros)")
    else:
        print(f"❌ CRÍTICO! {valid_count} textos (filtros muito rigorosos?)")

    print("=" * 80)


if __name__ == '__main__':
    main()
