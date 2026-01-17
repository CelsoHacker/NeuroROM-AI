#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translation Optimizer - Redução Agressiva de Workload
======================================================

Reduz 131.514 linhas para o mínimo traduzível através de:
- Deduplicação semântica
- Heurísticas de skip inteligente
- Cache por hash normalizado
- Agrupamento por contexto

Author: ROM Translation Framework
Version: 1.0.0
"""

import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict


class TranslationOptimizer:
    """Otimizador agressivo para redução de workload de tradução."""

    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize optimizer.

        Args:
            cache_file: Path to cache file (optional)
        """
        self.cache_file = cache_file or "translation_cache.json"
        self.cache = self._load_cache()

        # Estatísticas
        self.stats = {
            'original_count': 0,
            'deduplicated': 0,
            'skipped_technical': 0,
            'skipped_entropy': 0,
            'skipped_proper_nouns': 0,
            'skipped_no_vowels': 0,        # NOVO
            'skipped_repetition': 0,       # NOVO
            'skipped_too_short': 0,        # NOVO
            'binary_garbage': 0,           # NOVO
            'cache_hits': 0,
            'final_count': 0
        }

    def _load_cache(self) -> Dict[str, str]:
        """Load translation cache from disk."""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_cache(self):
        """Save translation cache to disk."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erro ao salvar cache: {e}")

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for deduplication.

        Removes variables, whitespace differences, etc.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        # Remove números (variáveis)
        text = re.sub(r'\d+', 'N', text)

        # Normaliza espaços
        text = re.sub(r'\s+', ' ', text).strip()

        # Case insensitive
        text = text.lower()

        # Remove pontuação final
        text = re.sub(r'[.!?]+$', '', text)

        return text

    def compute_hash(self, text: str) -> str:
        """
        Compute hash for normalized text.

        Args:
            text: Input text

        Returns:
            MD5 hash
        """
        normalized = self.normalize_text(text)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def is_technical_string(self, text: str) -> bool:
        """
        Check if text is a technical string (should skip translation).

        Args:
            text: Input text

        Returns:
            True if technical string
        """
        text = text.strip()

        # IDs numéricos (deve ter números E underscores/hífens para ser ID)
        # Palavras normais em MAIÚSCULAS (POWER, JUMP) NÃO são técnicas
        if re.match(r'^[A-Z0-9_\-]+$', text) and (re.search(r'\d', text) or re.search(r'[_\-]', text)):
            return True

        # Paths e URLs
        if '/' in text or '\\' in text or '.exe' in text.lower() or '.dll' in text.lower():
            return True

        # Comandos de código
        if text.startswith(('cmd_', 'func_', 'var_', 'id_')):
            return True

        # Placeholders vazios
        if re.match(r'^[{}\[\]<>]+$', text):
            return True

        # Apenas símbolos ou números
        if not re.search(r'[a-zA-Z]', text):
            return True

        return False

    def is_proper_noun(self, text: str) -> bool:
        """
        Heurística simples para detectar nomes próprios.

        Args:
            text: Input text

        Returns:
            True if likely a proper noun
        """
        text = text.strip()

        # Nome curto com maiúscula (provável nome)
        if len(text.split()) <= 2 and text[0].isupper():
            # Não tem artigos/preposições comuns
            if not any(word in text.lower() for word in ['the', 'a', 'an', 'of', 'in', 'on']):
                return True

        # Nome totalmente maiúsculo (sigla ou nome)
        if text.isupper() and len(text) >= 2 and len(text) <= 20:
            return True

        return False

    def calculate_entropy(self, text: str) -> float:
        """
        Calculate linguistic entropy (variação de caracteres).

        Textos com baixa entropia são geralmente lixo.

        Args:
            text: Input text

        Returns:
            Entropy value (0-1)
        """
        if not text:
            return 0.0

        # Conta caracteres únicos
        unique_chars = len(set(text.lower()))
        total_chars = len(text)

        return unique_chars / total_chars if total_chars > 0 else 0.0

    def is_no_vowels_garbage(self, text: str) -> bool:
        """
        REGRA DA VOGAL: Detecta strings sem vogais (lixo binário).

        Exceções: Siglas comuns de RPG (HP, MP, XP, LV, etc.)

        Args:
            text: Input text

        Returns:
            True if garbage (no vowels and not a common acronym)
        """
        text_clean = text.strip().upper()

        # Exceções: Siglas comuns de jogos
        common_acronyms = {
            'HP', 'MP', 'XP', 'SP', 'AP', 'DP', 'ATK', 'DEF', 'STR', 'VIT',
            'INT', 'DEX', 'AGI', 'LUK', 'LV', 'EXP', 'RPG', 'NPC', 'CPU',
            'P1', 'P2', 'P3', 'P4', 'FPS', 'BGM', 'SFX', 'HUD'
        }

        if text_clean in common_acronyms:
            return False

        # Verifica se tem pelo menos uma vogal
        vowels = set('aeiouAEIOUàáâãéêíóôõúÀÁÂÃÉÊÍÓÔÕÚ')
        has_vowel = any(char in vowels for char in text)

        return not has_vowel

    def is_repetition_garbage(self, text: str) -> bool:
        """
        REGRA DA REPETIÇÃO: Detecta padrões repetitivos (AAAAAA, ......).

        Args:
            text: Input text

        Returns:
            True if repetitive garbage
        """
        text_clean = text.strip()

        if len(text_clean) < 3:
            return False

        # Detecta repetição de um único caractere (AAAAA, ....., -----)
        if len(set(text_clean)) == 1:
            return True

        # Detecta padrões muito repetitivos (>70% é o mesmo caractere)
        most_common_char = max(set(text_clean), key=text_clean.count)
        repetition_ratio = text_clean.count(most_common_char) / len(text_clean)

        if repetition_ratio > 0.7:
            return True

        return False

    def is_too_short_garbage(self, text: str) -> bool:
        """
        REGRA DO TAMANHO: Descarta strings muito curtas (<3 chars).

        Exceções: Palavras comuns de menu (No, Lv, Ok, HP, etc.)

        Args:
            text: Input text

        Returns:
            True if too short and not a valid short word
        """
        text_clean = text.strip()

        if len(text_clean) >= 3:
            return False  # Tamanho OK

        # Exceções: Palavras curtas válidas de jogos/menus
        valid_short_words = {
            'No', 'Ok', 'Lv', 'HP', 'MP', 'XP', 'SP', 'AP',
            'P1', 'P2', 'Go', 'Up', 'On', 'If', 'Or', 'At',
            'To', 'In', 'Of', 'By', 'For'
        }

        # Case-insensitive check
        if text_clean in valid_short_words or text_clean.upper() in valid_short_words:
            return False

        # Muito curto e não é exceção
        return True

    def optimize_text_list(self,
                          texts: List[str],
                          skip_technical: bool = True,
                          skip_proper_nouns: bool = False,
                          min_entropy: float = 0.3,
                          use_cache: bool = True) -> Tuple[List[str], Dict[str, int]]:
        """
        Optimize text list for translation.

        Args:
            texts: List of texts to translate
            skip_technical: Skip technical strings
            skip_proper_nouns: Skip proper nouns
            min_entropy: Minimum entropy threshold
            use_cache: Use translation cache

        Returns:
            Tuple of (optimized_texts, index_mapping)
        """
        self.stats['original_count'] = len(texts)

        # Mapeamento: hash normalizado -> lista de índices originais
        hash_to_indices = defaultdict(list)

        # Textos únicos a traduzir
        unique_texts = []
        unique_hashes = set()

        # Índice reverso: qual índice do unique_texts usar para cada índice original
        index_mapping = {}

        for i, text in enumerate(texts):
            text = text.strip()

            # FILTRO 1: Técnico
            if skip_technical and self.is_technical_string(text):
                self.stats['skipped_technical'] += 1
                index_mapping[i] = -1  # -1 = usar original
                continue

            # FILTRO 2: Nomes próprios
            if skip_proper_nouns and self.is_proper_noun(text):
                self.stats['skipped_proper_nouns'] += 1
                index_mapping[i] = -1
                continue

            # FILTRO 3: Entropia baixa (lixo)
            entropy = self.calculate_entropy(text)
            if entropy < min_entropy:
                self.stats['skipped_entropy'] += 1
                index_mapping[i] = -1
                continue

            # FILTRO 4: Sem vogais (lixo binário)
            if self.is_no_vowels_garbage(text):
                self.stats['skipped_no_vowels'] += 1
                self.stats['binary_garbage'] += 1
                index_mapping[i] = -1
                continue

            # FILTRO 5: Repetição (AAAAA, .....)
            if self.is_repetition_garbage(text):
                self.stats['skipped_repetition'] += 1
                self.stats['binary_garbage'] += 1
                index_mapping[i] = -1
                continue

            # FILTRO 6: Muito curto (<3 chars)
            if self.is_too_short_garbage(text):
                self.stats['skipped_too_short'] += 1
                index_mapping[i] = -1
                continue

            # FILTRO 7: Cache
            text_hash = self.compute_hash(text)
            if use_cache and text_hash in self.cache:
                self.stats['cache_hits'] += 1
                # Retorna tradução do cache diretamente
                index_mapping[i] = -2  # -2 = usar cache
                continue

            # FILTRO 8: Deduplicação semântica
            if text_hash in unique_hashes:
                # Já existe, mapeia para o índice existente
                existing_idx = len([h for h in unique_hashes if h != text_hash])
                # Encontra o índice correto
                for idx, unique_text in enumerate(unique_texts):
                    if self.compute_hash(unique_text) == text_hash:
                        index_mapping[i] = idx
                        hash_to_indices[text_hash].append(i)
                        self.stats['deduplicated'] += 1
                        break
            else:
                # Novo texto único
                unique_hashes.add(text_hash)
                index_mapping[i] = len(unique_texts)
                unique_texts.append(text)
                hash_to_indices[text_hash].append(i)

        self.stats['final_count'] = len(unique_texts)

        return unique_texts, index_mapping

    def reconstruct_translations(self,
                                unique_translations: List[str],
                                original_texts: List[str],
                                index_mapping: Dict[str, int]) -> List[str]:
        """
        Reconstruct full translation list from optimized translations.

        Args:
            unique_translations: Translations of unique texts
            original_texts: Original text list
            index_mapping: Mapping from optimize_text_list

        Returns:
            Full translation list matching original_texts length
        """
        result = []

        for i, original_text in enumerate(original_texts):
            mapping_idx = index_mapping.get(i, -1)

            if mapping_idx == -1:
                # Usar texto original (técnico, nome próprio, etc)
                result.append(original_text)
            elif mapping_idx == -2:
                # Usar cache
                text_hash = self.compute_hash(original_text)
                cached = self.cache.get(text_hash, original_text)
                result.append(cached)
            elif mapping_idx >= 0 and mapping_idx < len(unique_translations):
                # Usar tradução
                translation = unique_translations[mapping_idx]

                # Atualiza cache
                text_hash = self.compute_hash(original_text)
                self.cache[text_hash] = translation

                result.append(translation)
            else:
                # Fallback
                result.append(original_text)

        return result

    def get_stats_report(self) -> str:
        """Generate statistics report."""
        reduction_percent = 100 * (1 - self.stats['final_count'] / self.stats['original_count']) if self.stats['original_count'] > 0 else 0

        # Calcula totais
        garbage_total = self.stats['binary_garbage']
        useful_total = self.stats['final_count']

        report = f"""
╔══════════════════════════════════════════════════════════╗
║         OTIMIZAÇÃO DE TRADUÇÃO - RELATÓRIO              ║
╚══════════════════════════════════════════════════════════╝

📊 REDUÇÃO DE WORKLOAD:
  • Textos originais:      {self.stats['original_count']:,}
  • Textos a traduzir:     {self.stats['final_count']:,}
  • Redução:               {reduction_percent:.1f}%

🗑️  FILTROS APLICADOS:
  • Deduplicados:          {self.stats['deduplicated']:,}
  • Strings técnicas:      {self.stats['skipped_technical']:,}
  • Nomes próprios:        {self.stats['skipped_proper_nouns']:,}
  • Baixa entropia:        {self.stats['skipped_entropy']:,}
  • Cache hits:            {self.stats['cache_hits']:,}

🚫 LIXO BINÁRIO DETECTADO (NOVOS FILTROS):
  • Sem vogais:            {self.stats['skipped_no_vowels']:,}
  • Repetição:             {self.stats['skipped_repetition']:,}
  • Muito curto:           {self.stats['skipped_too_short']:,}
  • TOTAL lixo binário:    {garbage_total:,}

✅ QUALIDADE:
  • Lixo Binário Detectado e Descartado: {garbage_total:,} linhas
  • Texto Útil Preservado: {useful_total:,} linhas

⏱️  ESTIMATIVA DE TEMPO:
  • Tempo antes:          {self.stats['original_count'] * 1.5 / 60:.1f} min
  • Tempo depois:         {self.stats['final_count'] * 1.5 / 60:.1f} min
  • Economia:             {(self.stats['original_count'] - self.stats['final_count']) * 1.5 / 60:.1f} min
"""
        return report


def main():
    """CLI interface for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python translation_optimizer.py <input_file>")
        return

    input_file = sys.argv[1]

    print("📖 Carregando arquivo...")
    with open(input_file, 'r', encoding='utf-8') as f:
        texts = [line.strip() for line in f.readlines()]

    print(f"   {len(texts):,} linhas carregadas\n")

    optimizer = TranslationOptimizer()

    print("🔧 Otimizando...")
    unique_texts, mapping = optimizer.optimize_text_list(texts)

    print(optimizer.get_stats_report())

    # Salva textos únicos
    output_file = input_file.replace('.txt', '_unique.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_texts))

    print(f"💾 Textos únicos salvos em: {output_file}")

    optimizer.save_cache()
    print(f"💾 Cache salvo em: {optimizer.cache_file}")


if __name__ == '__main__':
    main()
