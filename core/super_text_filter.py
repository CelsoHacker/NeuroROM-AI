# -*- coding: utf-8 -*-
"""
SUPER TEXT FILTER - Filtro Ultra-Agressivo de Lixo
===================================================
Remove 99% do lixo, mantém apenas TEXTO PURO EM INGLÊS.

Autor: Sistema de Tradução de ROMs V5
Data: 2026-01
"""

import re
from typing import List, Tuple, Set
from collections import Counter


# ============================================================================
# DICIONÁRIO DE PALAVRAS INGLESAS COMUNS
# ============================================================================

COMMON_ENGLISH_WORDS = {
    # Artigos, preposições, conjunções
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'after',
    'over', 'between', 'out', 'against', 'during', 'without', 'before',
    'under', 'around', 'among',

    # Pronomes
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
    'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'this', 'that', 'these', 'those', 'who', 'what', 'which', 'where',
    'when', 'why', 'how',

    # Verbos comuns
    'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
    'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'may', 'might', 'must', 'can', 'go', 'get', 'make', 'take', 'come',
    'see', 'know', 'think', 'look', 'want', 'give', 'use', 'find', 'tell',
    'ask', 'work', 'seem', 'feel', 'try', 'leave', 'call', 'keep', 'let',
    'begin', 'help', 'show', 'hear', 'play', 'run', 'move', 'like', 'live',
    'believe', 'hold', 'bring', 'happen', 'write', 'provide', 'sit', 'stand',
    'lose', 'pay', 'meet', 'include', 'continue', 'set', 'learn', 'change',
    'lead', 'understand', 'watch', 'follow', 'stop', 'create', 'speak', 'read',
    'allow', 'add', 'spend', 'grow', 'open', 'walk', 'win', 'offer', 'remember',
    'love', 'consider', 'appear', 'buy', 'wait', 'serve', 'die', 'send', 'expect',
    'build', 'stay', 'fall', 'cut', 'reach', 'kill', 'remain', 'suggest', 'raise',
    'pass', 'sell', 'require', 'report', 'decide', 'pull',

    # Substantivos comuns
    'time', 'year', 'people', 'way', 'day', 'man', 'thing', 'woman', 'life',
    'child', 'world', 'school', 'state', 'family', 'student', 'group', 'country',
    'problem', 'hand', 'part', 'place', 'case', 'week', 'company', 'system',
    'program', 'question', 'work', 'government', 'number', 'night', 'point',
    'home', 'water', 'room', 'mother', 'area', 'money', 'story', 'fact', 'month',
    'lot', 'right', 'study', 'book', 'eye', 'job', 'word', 'business', 'issue',
    'side', 'kind', 'head', 'house', 'service', 'friend', 'father', 'power',
    'hour', 'game', 'line', 'end', 'member', 'law', 'car', 'city', 'community',
    'name', 'president', 'team', 'minute', 'idea', 'kid', 'body', 'information',
    'back', 'parent', 'face', 'others', 'level', 'office', 'door', 'health',
    'person', 'art', 'war', 'history', 'party', 'result', 'change', 'morning',
    'reason', 'research', 'girl', 'guy', 'moment', 'air', 'teacher', 'force',
    'education',

    # Adjetivos comuns
    'good', 'new', 'first', 'last', 'long', 'great', 'little', 'own', 'other',
    'old', 'right', 'big', 'high', 'different', 'small', 'large', 'next', 'early',
    'young', 'important', 'few', 'public', 'bad', 'same', 'able', 'all', 'each',
    'every', 'both', 'many', 'much', 'more', 'most', 'some', 'any', 'no', 'such',
    'full', 'true', 'real', 'best', 'better', 'sure', 'free', 'whole', 'several',
    'main', 'hard', 'simple', 'certain', 'clear', 'strong', 'special', 'easy',
    'ready', 'blue', 'red', 'green', 'black', 'white',

    # Advérbios comuns
    'not', 'now', 'very', 'also', 'just', 'only', 'well', 'even', 'back', 'still',
    'so', 'then', 'too', 'always', 'never', 'really', 'often', 'probably', 'already',
    'quite', 'yet', 'almost', 'today', 'together', 'again', 'perhaps', 'maybe',
    'sometimes', 'however', 'later', 'especially', 'actually', 'though', 'therefore',

    # Palavras comuns de jogos retro
    'act', 'map', 'hp', 'mp', 'exp', 'hero', 'princess', 'dragon', 'enemy', 'boss', 'star',
    'coin', 'coins', 'lives', 'life', 'player', 'game', 'world', 'level', 'stage',
    'start', 'select', 'continue', 'exit', 'save', 'load', 'file', 'bonus',
    'score', 'points', 'time', 'end', 'over', 'won', 'lost', 'try', 'again',
    'press', 'button', 'jump', 'run', 'walk', 'fire', 'power', 'up', 'down',
    'left', 'right', 'pause', 'menu', 'options', 'settings', 'sound', 'music',
    'volume', 'controller', 'game', 'play', 'top', 'bottom', 'castle', 'ghost',
    'house', 'forest', 'valley', 'mountain', 'island', 'water', 'land', 'special',
    'way', 'course', 'clear', 'goal', 'congratulations', 'thanks', 'welcome',
    'hello', 'goodbye', 'yes', 'no', 'ok', 'okay', 'thank', 'please', 'sorry',
    'here', 'there', 'next', 'previous', 'back', 'forward', 'one', 'two', 'three',
    'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',

    # Nomes de jogos/personagens/empresas famosos
    'mario', 'luigi', 'sonic', 'tails', 'knuckles', 'zelda', 'link', 'samus',
    'megaman', 'rockman', 'super', 'ultra', 'hyper', 'turbo', 'pro', 'deluxe',
    'alex', 'kidd', 'shinobi', 'streets', 'rage', 'golden', 'axe', 'altered',
    'beast', 'phantasy', 'shining', 'force', 'wonder', 'boy', 'fantasy', 'zone',
    # Empresas de jogos
    'sega', 'nintendo', 'capcom', 'konami', 'namco', 'taito', 'atari', 'snk',
    'tecmo', 'koei', 'enix', 'squaresoft', 'square', 'hudson', 'irem', 'jaleco',
    'sunsoft', 'technos', 'tradewest', 'acclaim', 'activision', 'data', 'east',
    # Nomes japoneses comuns em créditos
    'hayashi', 'yamamoto', 'tanaka', 'suzuki', 'takahashi', 'watanabe', 'nakamura',
    'kobayashi', 'yoshida', 'yamada', 'sasaki', 'yamaguchi', 'matsumoto', 'kimura',
}

# Adiciona variações com maiúsculas
COMMON_ENGLISH_WORDS.update({word.upper() for word in COMMON_ENGLISH_WORDS})
COMMON_ENGLISH_WORDS.update({word.capitalize() for word in COMMON_ENGLISH_WORDS})


# ============================================================================
# TRIGRAMAS COMUNS DO INGLÊS (para validação de estrutura)
# ============================================================================

COMMON_ENGLISH_TRIGRAMS = {
    # Top 50 trigramas mais comuns em inglês
    'the', 'and', 'ing', 'ion', 'tio', 'ent', 'ati', 'for', 'her', 'ter',
    'hat', 'tha', 'ere', 'ate', 'his', 'con', 'res', 'ver', 'all', 'ons',
    'nce', 'men', 'ith', 'ted', 'ers', 'pro', 'thi', 'wit', 'are', 'ess',
    'not', 'ive', 'was', 'ect', 'rea', 'com', 'eve', 'per', 'int', 'est',
    'sta', 'cti', 'ica', 'ist', 'ear', 'ain', 'one', 'our', 'iti', 'rat',
    # Trigramas adicionais comuns em jogos
    'you', 'can', 'get', 'has', 'him', 'out', 'way', 'new', 'now', 'old',
    'see', 'use', 'two', 'how', 'boy', 'did', 'its', 'let', 'put', 'say',
    'she', 'too', 'any', 'day', 'got', 'had', 'hey', 'man', 'run', 'end',
    'far', 'big', 'guy', 'may', 'own', 'try', 'ago', 'bad', 'buy', 'cut',
    'low', 'off', 'set', 'top', 'yes', 'yet', 'ask', 'bet', 'bit', 'box',
    # Terminações comuns
    'ble', 'ful', 'ess', 'ous', 'ive', 'ant', 'ent', 'ism', 'ist', 'ity',
    'ade', 'age', 'ure', 'ine', 'ose', 'ude', 'ard', 'dom', 'eer', 'ery',
    # Prefixos comuns
    'pre', 'pro', 'sub', 'sup', 'dis', 'mis', 'non', 'out', 'per', 'ove',
    'und', 'unt', 'upp', 'aft', 'bef', 'bet', 'dow', 'mid', 'abo', 'aro',
}


# ============================================================================
# SUPER TEXT FILTER - CLASSE PRINCIPAL
# ============================================================================

class SuperTextFilter:
    """
    Filtro ultra-agressivo que remove 99% do lixo.
    Mantém apenas texto que parece inglês real.
    """

    def __init__(self):
        self.vowels = set('aeiouAEIOU')
        self.consonants = set('bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ')
        self.english_words = COMMON_ENGLISH_WORDS

    # ========================================================================
    # FILTROS INDIVIDUAIS
    # ========================================================================

    def has_minimum_vowels(self, text: str, min_vowels: int = 3) -> bool:
        """Texto real deve ter pelo menos 3 vogais."""
        vowel_count = sum(1 for c in text if c in self.vowels)
        return vowel_count >= min_vowels

    def has_excessive_repetition(self, text: str, max_repeat: int = 2) -> bool:
        """
        Detecta repetição excessiva de caracteres.
        Exemplos: JJJ, AAA, BBB são lixo.
        """
        # Remove espaços para análise
        clean = text.replace(' ', '').replace('-', '')

        if len(clean) < 3:
            return False

        # Conta repetições consecutivas
        for i in range(len(clean) - max_repeat):
            if clean[i] == clean[i+1] == clean[i+2]:
                return True

        return False

    def has_too_many_uppercase(self, text: str, max_ratio: float = 0.85) -> bool:
        """
        Detecta strings só com maiúsculas sem sentido.
        Exemplos: MKEI, DEFEM são lixo.
        Exceções: títulos de jogos, palavras conhecidas.
        """
        letters = [c for c in text if c.isalpha()]

        if len(letters) < 3:
            return False

        uppercase_count = sum(1 for c in letters if c.isupper())
        ratio = uppercase_count / len(letters)

        # Se tem mais de 85% maiúsculas, verifica se tem palavras inglesas
        if ratio > max_ratio:
            # Se tem palavra inglesa conhecida, está OK (títulos de jogos)
            if self.has_english_word(text):
                return False

            # Se não tem palavra conhecida, é lixo
            return True

        return False

    def has_english_word(self, text: str) -> bool:
        """
        Verifica se a string contém pelo menos UMA palavra inglesa real.
        Também detecta palavras compostas (HEROWORLD = HERO + WORLD).
        Aceita nomes próprios com boa estrutura fonética.
        """
        text_lower = text.lower()

        # Método 1: Separa em palavras por espaço
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text_lower)

        # Verifica se alguma palavra é conhecida
        for word in words:
            if word in self.english_words:
                return True

        # Método 2: Detecta substrings conhecidas (para palavras compostas)
        # Exemplo: "heroworld" contém "hero" e "world"
        for known_word in self.english_words:
            if len(known_word) >= 4:  # Só palavras de 4+ letras
                if known_word.lower() in text_lower:
                    return True

        # Método 3: Aceita nomes próprios com boa estrutura fonética
        # Exemplo: "Hayashi" tem vogais bem distribuídas (padrão CV-CV-CV)
        for word in words:
            if len(word) >= 5:
                vowel_count = sum(1 for c in word if c in 'aeiou')
                vowel_ratio = vowel_count / len(word)
                # Nomes próprios geralmente têm 25-55% de vogais
                if 0.25 <= vowel_ratio <= 0.55:
                    # Verifica se tem pelo menos 1 trigrama comum
                    has_trigram = False
                    for i in range(len(word) - 2):
                        if word[i:i+3] in COMMON_ENGLISH_TRIGRAMS:
                            has_trigram = True
                            break
                    if has_trigram:
                        return True

                    # OU se tem padrão consoante-vogal alternado (nomes japoneses)
                    # Exemplo: Ha-ya-shi, Ma-ri-o, So-ni-c
                    cv_pattern = 0
                    for i in range(len(word) - 1):
                        c1_is_vowel = word[i] in 'aeiou'
                        c2_is_vowel = word[i+1] in 'aeiou'
                        if c1_is_vowel != c2_is_vowel:
                            cv_pattern += 1
                    # Se mais de 60% do texto alterna vogal/consoante
                    if cv_pattern / (len(word) - 1) >= 0.6:
                        return True

        return False

    def has_binary_garbage(self, text: str) -> bool:
        """
        Detecta lixo binário/ponteiros: |}{][\
        Se >40% são esses símbolos, é lixo.
        """
        garbage_chars = set('|}{][\\')
        garbage_count = sum(1 for c in text if c in garbage_chars)

        if len(text) > 0 and garbage_count / len(text) > 0.4:
            return True

        return False

    def has_human_structure(self, text: str) -> bool:
        """
        Verifica se o texto tem estrutura humana:
        - Palavras separadas por espaços
        - Pontuação adequada
        - Alternância vogal/consoante
        """
        # Deve ter pelo menos uma palavra de 3+ letras
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        if not words:
            return False

        # Verifica alternância vogal/consoante em pelo menos uma palavra
        for word in words:
            vowel_positions = [i for i, c in enumerate(word) if c.lower() in 'aeiou']
            consonant_positions = [i for i, c in enumerate(word) if c.lower() in 'bcdfghjklmnpqrstvwxyz']

            # Deve ter vogais E consoantes
            if len(vowel_positions) >= 1 and len(consonant_positions) >= 2:
                return True

        return False

    def is_single_letter_garbage(self, text: str) -> bool:
        """
        Detecta lixo de letras únicas ou pares sem sentido.
        Exemplos: bLz, cUk, sB9
        """
        clean = text.strip()

        # Remove números e pontuação
        letters_only = re.sub(r'[^a-zA-Z]', '', clean)

        # Se tem menos de 3 letras, provavelmente é lixo
        if len(letters_only) < 3:
            return True

        # Se tem 3-4 letras mas não forma palavra conhecida
        if len(letters_only) <= 4:
            if letters_only.lower() not in self.english_words:
                return True

        return False

    def has_only_symbols(self, text: str) -> bool:
        """
        Detecta strings que são apenas símbolos/números.
        Exemplos: 0088@, }{, @@@
        """
        letters = [c for c in text if c.isalpha()]
        return len(letters) < 3

    def is_pattern_garbage(self, text: str) -> bool:
        """
        Detecta padrões específicos de lixo:
        - Sequências alfabéticas: ABC, DEF
        - Sequências numéricas: 012, 345
        - Padrões de offset: 0x, [, ]
        """
        clean = text.strip()

        # Padrões de offset
        if clean.startswith('[') or clean.startswith('0x'):
            return True

        # Sequências alfabéticas (3+ letras consecutivas)
        if re.search(r'[a-zA-Z]{3}', clean):
            for i in range(len(clean) - 2):
                if clean[i:i+3].isalpha():
                    chars = clean[i:i+3].upper()
                    if ord(chars[1]) == ord(chars[0]) + 1 and ord(chars[2]) == ord(chars[1]) + 1:
                        return True

        # Sequências numéricas
        if re.search(r'\d{3,}', clean):
            numbers = re.findall(r'\d{3,}', clean)
            for num_str in numbers:
                for i in range(len(num_str) - 2):
                    if int(num_str[i+1]) == int(num_str[i]) + 1 and int(num_str[i+2]) == int(num_str[i+1]) + 1:
                        return True

        return False

    # ========================================================================
    # NOVOS FILTROS V6 - Melhorias para eliminar lixo binário
    # ========================================================================

    def has_valid_vowel_ratio(self, text: str) -> bool:
        """
        Verifica proporção de vogais. Inglês real tem ~38-40% vogais.
        Mínimo aceitável: 15% para permitir siglas e nomes próprios.
        Rejeita: 'jtkem' (20% vogais, mas sem estrutura), 'KOYQ' (25%)
        """
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 4:
            return True  # Muito curto para validar por proporção

        vowel_count = sum(1 for c in letters if c.lower() in 'aeiou')
        ratio = vowel_count / len(letters)

        # Mínimo 15% vogais para texto real
        return ratio >= 0.15

    def has_symbols_between_letters(self, text: str) -> bool:
        """
        Detecta símbolos intercalados com letras - típico de dados binários.
        Exemplos: E(EHE, A@B, X]Y são lixo.
        Exceções: contrações (it's, don't) e pontuação normal.
        """
        # Padrão: letra + símbolo não-comum + letra
        # Símbolos permitidos entre letras: ' - (para contrações e hífens)
        garbage_pattern = r"[A-Za-z][\(\)\[\]\{\}\|\\@#\$%\^&\*\+\=\<\>][A-Za-z]"
        return bool(re.search(garbage_pattern, text))

    def has_chaotic_case(self, text: str) -> bool:
        """
        Detecta alternância caótica de maiúsculas/minúsculas.
        Exemplos: EhEhE, AbCdE, FbDDQ são lixo (dados de tiles).
        Exceções: CamelCase normal (iPhone, McDonald)
        """
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 4:
            return False

        # Conta mudanças de case
        changes = 0
        for i in range(len(letters) - 1):
            if letters[i].isupper() != letters[i + 1].isupper():
                changes += 1

        # Se mais de 40% são mudanças de case, é caótico
        change_ratio = changes / (len(letters) - 1)

        # Padrão específico: letra maiúscula-minúscula-maiúscula repetido
        if change_ratio > 0.4:
            # Verifica se é CamelCase legítimo (tem palavra inglesa)
            if self.has_english_word(text):
                return False
            return True

        return False

    def has_valid_trigrams(self, text: str) -> bool:
        """
        Verifica se contém trigramas comuns do inglês.
        Texto real deve ter pelo menos 1 trigrama comum.
        Rejeita: 'jtkem' (nenhum trigrama comum), 'KOYQ' (nenhum)
        """
        text_lower = text.lower()
        letters_only = ''.join(c for c in text_lower if c.isalpha())

        # Só valida strings de 5+ caracteres
        if len(letters_only) < 5:
            return True  # Muito curto para validar

        # Procura pelo menos 1 trigrama comum
        for i in range(len(letters_only) - 2):
            trigram = letters_only[i:i + 3]
            if trigram in COMMON_ENGLISH_TRIGRAMS:
                return True

        return False

    def is_medium_word_garbage(self, text: str) -> bool:
        """
        Detecta palavras de 5-8 caracteres que não são inglês válido.
        Complementa is_single_letter_garbage que só pega até 4 chars.
        Exemplos: 'jtkem', 'KOYQ' são lixo.
        """
        clean = text.strip()
        letters_only = re.sub(r'[^a-zA-Z]', '', clean)

        # Foca em palavras de 5-8 letras sem espaços
        if 5 <= len(letters_only) <= 8 and ' ' not in clean:
            # Deve ter trigrama válido OU ser palavra conhecida
            if not self.has_valid_trigrams(text):
                if letters_only.lower() not in self.english_words:
                    return True

        return False

    # ========================================================================
    # FILTROS V6.1 - MAESTRIA MASTER SYSTEM (Deep Clean Mode)
    # ========================================================================

    def has_repetitive_bigrams(self, text: str) -> bool:
        """
        Detecta repetições rítmicas típicas de tiles gráficos.
        Exemplos: EFEF, CNCN, NGKNKFKN, MLM/L/L/L, COCNCNCN

        No inglês real, bigramas raramente repetem 3+ vezes.
        No lixo de ROM, isso acontece constantemente.
        """
        # Limpa mantendo apenas alfanuméricos e alguns símbolos comuns em lixo
        clean_text = ''.join(c for c in text if c.isalnum() or c in '/;?')

        if len(clean_text) < 6:
            return False

        clean_lower = clean_text.lower()

        # Verifica Bigramas (Ex: 'ef', 'cn', 'l/', 'kn')
        bigram_counts = {}
        for i in range(len(clean_lower) - 1):
            bigram = clean_lower[i:i+2]
            # Ignora bigramas com mesmo caractere (aa, bb)
            if bigram[0] != bigram[1]:
                bigram_counts[bigram] = bigram_counts.get(bigram, 0) + 1

        # Se qualquer bigrama repete 3+ vezes, é lixo
        for bigram, count in bigram_counts.items():
            if count >= 3:
                return True

        # Verifica Trigramas repetidos (Ex: 'coc', 'knk')
        if len(clean_lower) > 8:
            trigram_counts = {}
            for i in range(len(clean_lower) - 2):
                trigram = clean_lower[i:i+3]
                trigram_counts[trigram] = trigram_counts.get(trigram, 0) + 1

            for trigram, count in trigram_counts.items():
                if count >= 2:
                    return True

        return False

    def has_sega_garbage_density(self, text: str) -> bool:
        """
        Detecta strings com alta densidade de caracteres típicos de lixo Sega.

        Em ROMs de Master System/Mega Drive, tiles gráficos usam
        excessivamente as letras K, N, F, C, G, J, Q, X, Z.
        Texto real raramente tem >50% dessas letras.
        """
        # Caracteres que aparecem muito em lixo binário Sega
        garbage_alphabet = set('knfcgjqxz')

        text_lower = text.lower()
        letters_only = [c for c in text_lower if c.isalpha()]

        if len(letters_only) < 5:
            return False

        # Conta letras do "alfabeto de lixo"
        garbage_count = sum(1 for c in letters_only if c in garbage_alphabet)
        ratio = garbage_count / len(letters_only)

        # Se mais de 50% são letras de lixo, rejeita
        if ratio > 0.50:
            return True

        # Filtro extra: sequências sem vogais intercaladas
        # Ex: NGKNKF (N-G-K-N-K-F = 0 vogais em 6 letras consecutivas)
        max_consonant_run = 0
        current_run = 0
        vowels = set('aeiou')

        for c in letters_only:
            if c not in vowels:
                current_run += 1
                max_consonant_run = max(max_consonant_run, current_run)
            else:
                current_run = 0

        # Mais de 5 consoantes seguidas = lixo (inglês real: max ~4)
        if max_consonant_run > 5:
            return True

        return False

    def has_symbolic_rhythm(self, text: str) -> bool:
        """
        Detecta padrões rítmicos com símbolos.
        Exemplos: MLM/L/L/LO;O;O;OO, BDD?D?FF?DF?

        Símbolos em texto real são pontuação. Em lixo, são rítmicos.
        """
        # Conta símbolos
        symbols = set('/;?!')
        symbol_count = sum(1 for c in text if c in symbols)

        if symbol_count < 2:
            return False

        # Se tem muitos símbolos repetidos no mesmo padrão
        for sym in symbols:
            if text.count(sym) >= 3:
                # Verifica se estão em padrão rítmico (espaçamento regular)
                positions = [i for i, c in enumerate(text) if c == sym]
                if len(positions) >= 3:
                    # Calcula diferenças entre posições
                    diffs = [positions[i+1] - positions[i]
                             for i in range(len(positions)-1)]
                    # Se as diferenças são similares (ritmo), é lixo
                    if len(set(diffs)) <= 2:  # Max 2 espaçamentos diferentes
                        return True

        return False

    # ========================================================================
    # FILTRO PRINCIPAL
    # ========================================================================

    def is_valid_text(self, text: str, preservation_mode: bool = False) -> Tuple[bool, str]:
        """
        Aplica TODOS os filtros.

        Args:
            text: Texto a validar
            preservation_mode: Se True, usa filtros MUITO mais lenientes para preservar
                              diálogos de RPG com códigos de controle (MTE/DTE)

        Returns:
            (is_valid, reason)
        """
        if not text or len(text.strip()) < 3:
            return False, "muito curto"

        text = text.strip()

        # ===================================================================
        # MODO PRESERVAÇÃO (para MTE/DTE) - Apenas filtros básicos
        # ===================================================================
        if preservation_mode:
            # FILTRO 1: Apenas símbolos (mantém)
            if self.has_only_symbols(text):
                return False, "apenas símbolos/números"

            # FILTRO 2: Vogais insuficientes (relaxado: 1 vogal ao invés de 2)
            if not self.has_minimum_vowels(text, min_vowels=1):
                return False, "sem vogais"

            # FILTRO 3: Repetição excessiva (relaxado: permite até 4 repetições)
            if len(text.replace(' ', '')) >= 5:
                clean = text.replace(' ', '')
                has_extreme_repeat = False
                for i in range(len(clean) - 4):
                    if clean[i] == clean[i+1] == clean[i+2] == clean[i+3] == clean[i+4]:
                        has_extreme_repeat = True
                        break
                if has_extreme_repeat:
                    return False, "repetição extrema"

            # ✅ PASSOU NOS FILTROS BÁSICOS (Modo Preservação)
            return True, "VÁLIDO (modo preservação)"

        # ===================================================================
        # MODO NORMAL (padrão) - Filtros agressivos
        # ===================================================================

        # FILTRO 1: Apenas símbolos
        if self.has_only_symbols(text):
            return False, "apenas símbolos/números"

        # FILTRO 2: Vogais insuficientes (exceto palavras conhecidas)
        if not self.has_minimum_vowels(text, min_vowels=2):
            # Exceção: palavras curtas conhecidas (Act, HP, MP, etc.)
            if not self.has_english_word(text):
                return False, "sem vogais suficientes"

        # FILTRO 3: Repetição excessiva
        if self.has_excessive_repetition(text):
            return False, "caracteres repetidos (JJJ)"

        # FILTRO 4: Lixo de letras únicas
        if self.is_single_letter_garbage(text):
            return False, "letras isoladas sem sentido"

        # FILTRO 5: Lixo binário/ponteiros
        if self.has_binary_garbage(text):
            return False, "lixo binário (ponteiros)"

        # FILTRO 6: Padrões de lixo
        if self.is_pattern_garbage(text):
            return False, "padrão de lixo detectado"

        # FILTRO 7: Estrutura humana
        if not self.has_human_structure(text):
            return False, "sem estrutura humana"

        # FILTRO 8: Palavra inglesa (CRÍTICO) - deve vir antes de maiúsculas
        if not self.has_english_word(text):
            return False, "nenhuma palavra inglesa reconhecida"

        # FILTRO 9: Maiúsculas sem sentido (usa has_english_word internamente)
        if self.has_too_many_uppercase(text):
            return False, "maiúsculas sem sentido"

        # ===============================================================
        # NOVOS FILTROS V6 - Eliminam lixo como 'jtkem', 'E(EHEhE', 'KOYQ'
        # ===============================================================

        # FILTRO 10: Símbolos entre letras (E(EHE, A@B)
        if self.has_symbols_between_letters(text):
            return False, "símbolos intercalados (dados binários)"

        # FILTRO 11: Case caótico (EhEhE, AbCdE)
        if self.has_chaotic_case(text):
            return False, "alternância caótica maiúscula/minúscula"

        # FILTRO 12: Proporção de vogais inválida
        if not self.has_valid_vowel_ratio(text):
            return False, "proporção vogal/consoante inválida"

        # FILTRO 13: Trigramas inválidos para palavras médias
        if self.is_medium_word_garbage(text):
            return False, "palavra sem trigramas ingleses válidos"

        # ===============================================================
        # FILTROS V6.1 - MAESTRIA MASTER SYSTEM (Deep Clean Mode)
        # ===============================================================

        # FILTRO 14: Bigramas repetitivos (EFEF, CNCN, NGKNKFKN)
        if self.has_repetitive_bigrams(text):
            return False, "padrão rítmico de tiles (bigramas repetidos)"

        # FILTRO 15: Densidade de lixo Sega (K,N,F,C,G,J excessivos)
        if self.has_sega_garbage_density(text):
            return False, "densidade de caracteres típicos de lixo Sega"

        # FILTRO 16: Ritmo simbólico (MLM/L/L/L, O;O;O;O)
        if self.has_symbolic_rhythm(text):
            return False, "padrão rítmico com símbolos (tiles)"

        # PASSOU EM TODOS OS FILTROS!
        return True, "VÁLIDO"

    def filter_text_list(self, texts: List[str], show_stats: bool = True) -> Tuple[List[str], dict]:
        """
        Filtra lista de textos.

        Returns:
            (texts_válidos, estatísticas)
        """
        valid_texts = []
        rejection_reasons = Counter()

        for text in texts:
            is_valid, reason = self.is_valid_text(text)

            if is_valid:
                valid_texts.append(text)
            else:
                rejection_reasons[reason] += 1

        stats = {
            'total_input': len(texts),
            'total_valid': len(valid_texts),
            'total_rejected': len(texts) - len(valid_texts),
            'rejection_rate': (len(texts) - len(valid_texts)) / len(texts) * 100 if texts else 0,
            'rejection_reasons': dict(rejection_reasons.most_common(10))
        }

        if show_stats:
            print("="*80)
            print("🔥 SUPER TEXT FILTER - ESTATÍSTICAS")
            print("="*80)
            print(f"📥 Entrada: {stats['total_input']} strings")
            print(f"✅ Válidos: {stats['total_valid']} strings")
            print(f"❌ Rejeitados: {stats['total_rejected']} strings ({stats['rejection_rate']:.1f}%)")
            print("\n📊 RAZÕES DE REJEIÇÃO:")
            for reason, count in stats['rejection_reasons'].items():
                print(f"   • {reason}: {count} strings")
            print("="*80 + "\n")

        return valid_texts, stats


# ============================================================================
# FUNÇÃO AUXILIAR PARA ARQUIVO
# ============================================================================

def filter_extracted_file(input_file: str, output_file: str = None) -> dict:
    """
    Filtra arquivo de textos extraídos.

    Args:
        input_file: Arquivo com textos extraídos (formato [offset] text)
        output_file: Arquivo de saída (opcional, padrão: input_FILTERED.txt)

    Returns:
        Dicionário com estatísticas
    """
    if output_file is None:
        output_file = input_file.replace('.txt', '_FILTERED.txt')

    # Lê arquivo
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Separa header de textos
    header_lines = []
    text_lines = []

    for line in lines:
        if line.startswith('#') or not line.strip():
            header_lines.append(line)
        else:
            # Extrai texto (remove offset)
            if ']' in line:
                text = line.split(']', 1)[1].strip()
                if text:
                    text_lines.append((line, text))

    # Aplica filtro
    filter_obj = SuperTextFilter()

    valid_lines = []
    rejection_reasons = Counter()

    for original_line, text in text_lines:
        is_valid, reason = filter_obj.is_valid_text(text)

        if is_valid:
            valid_lines.append(original_line)
        else:
            rejection_reasons[reason] += 1

    # Salva resultado
    with open(output_file, 'w', encoding='utf-8') as f:
        # Escreve header atualizado
        f.write("# ROM Text Extraction Results - FILTERED\n")
        f.write("# ==========================================\n")
        f.write(f"# Original file: {input_file}\n")
        f.write(f"# Total strings found: {len(text_lines)}\n")
        f.write(f"# Valid strings: {len(valid_lines)}\n")
        f.write(f"# Rejection rate: {(len(text_lines) - len(valid_lines)) / len(text_lines) * 100:.1f}%\n")
        f.write("#\n")
        f.write("# Filter: SUPER TEXT FILTER (English words validation)\n")
        f.write("# ==========================================\n\n")

        # Escreve textos válidos
        for line in valid_lines:
            f.write(line)

    stats = {
        'input_file': input_file,
        'output_file': output_file,
        'total_input': len(text_lines),
        'total_valid': len(valid_lines),
        'total_rejected': len(text_lines) - len(valid_lines),
        'rejection_rate': (len(text_lines) - len(valid_lines)) / len(text_lines) * 100 if text_lines else 0,
        'rejection_reasons': dict(rejection_reasons.most_common(10))
    }

    # Mostra estatísticas
    print("="*80)
    print("🔥 SUPER TEXT FILTER - RESULTADO")
    print("="*80)
    print(f"📂 Arquivo: {input_file}")
    print(f"📥 Entrada: {stats['total_input']} strings")
    print(f"✅ Válidos: {stats['total_valid']} strings")
    print(f"❌ Rejeitados: {stats['total_rejected']} strings ({stats['rejection_rate']:.1f}%)")
    print(f"\n💾 Salvo em: {output_file}")
    print("\n📊 TOP 10 RAZÕES DE REJEIÇÃO:")
    for idx, (reason, count) in enumerate(stats['rejection_reasons'].items(), 1):
        print(f"   {idx}. {reason}: {count} strings ({count/stats['total_input']*100:.1f}%)")
    print("="*80 + "\n")

    return stats


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        filter_extracted_file(input_file, output_file)
    else:
        # Teste com exemplos de jogos retro
        test_strings = [
            "bLz",  # LIXO
            "JJJ",  # LIXO
            "SUPER HEROWORLD",  # VÁLIDO
            "drd}",  # LIXO
            "Press START",  # VÁLIDO
            "MKEI&E",  # LIXO
            "Hero saves Princess",  # VÁLIDO
            "0088@",  # LIXO
            "Game Over",  # VÁLIDO
            "ABC",  # LIXO (sequência)
            "Thanks for playing",  # VÁLIDO
            "kQmN",  # LIXO
        ]

        filter_obj = SuperTextFilter()

        print("="*80)
        print("🧪 TESTE DO SUPER TEXT FILTER")
        print("="*80 + "\n")

        for text in test_strings:
            is_valid, reason = filter_obj.is_valid_text(text)
            status = "✅ VÁLIDO" if is_valid else f"❌ {reason.upper()}"
            print(f"{status:50s} | {text}")

        print("\n" + "="*80)
