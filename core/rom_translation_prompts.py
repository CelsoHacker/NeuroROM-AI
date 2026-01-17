#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Translation Prompts - Prompts Técnicos sem Alucinação
==========================================================

Prompts especializados para tradução de ROMs que previnem:
- Invenção de traduções
- Recusas moralistas
- Alteração de códigos de controle
- Retorno de None

Author: ROM Translation Framework
Version: 1.0.0
"""


class ROMTranslationPrompts:
    """Prompts técnicos para tradução de ROMs."""

    # Estilos de localização por época
    STYLES = {
        "anos_80": {
            "name": "Anos 80",
            "description": "Estilo arcade e 8-bit",
            "prompt_addon": """STYLE: 1980s arcade/8-bit localization.
- Very short text (hardware limits)
- Simple vocabulary
- Direct instructions
- No articles when possible"""
        },
        "anos_90": {
            "name": "Anos 90",
            "description": "Era SNES/Mega Drive",
            "prompt_addon": """STYLE: Classic 90s Brazilian localization.
- Sound like official SNES/Genesis translations
- Natural Brazilian Portuguese, not literal
- Short sentences (ROM space limits)
- No modern slang, no emojis
- Use period-appropriate vocabulary"""
        },
        "anos_2000": {
            "name": "Anos 2000",
            "description": "Era PS1/PS2/N64",
            "prompt_addon": """STYLE: 2000s Brazilian localization.
- More text space available
- Natural dialogue flow
- Can use longer sentences
- Keep era-appropriate vocabulary"""
        },
        "moderno": {
            "name": "Moderno (2010-2026)",
            "description": "Português atual",
            "prompt_addon": """STYLE: Modern Brazilian Portuguese.
- Natural and fluid language
- Contemporary vocabulary
- Maintain original tone and emotion"""
        },
        "literal": {
            "name": "Literal",
            "description": "Tradução fiel ao original",
            "prompt_addon": """STYLE: Literal translation.
- Stay close to original meaning
- Preserve sentence structure
- Minimal interpretation"""
        }
    }

    # Contextos de gênero completos
    GENRES = {
        "auto": {"name": "Auto-detectar", "context": ""},
        "rpg": {
            "name": "RPG",
            "context": "GENRE: RPG. Epic immersive language. Respect universe terms."
        },
        "acao": {
            "name": "Ação/Aventura",
            "context": "GENRE: Action/Adventure. Dynamic exciting text. Quick clear dialogue."
        },
        "estrategia": {
            "name": "Estratégia",
            "context": "GENRE: Strategy. Clear tactical terms. Precise instructions."
        },
        "luta": {
            "name": "Luta",
            "context": "GENRE: Fighting. Short impactful phrases. Combat terminology."
        },
        "guerra": {
            "name": "Guerra",
            "context": "GENRE: War. Military terminology. Serious dramatic tone."
        },
        "terror": {
            "name": "Terror",
            "context": "GENRE: Horror. Tense atmosphere. Short dark sentences."
        },
        "tiro": {
            "name": "Tiro/FPS",
            "context": "GENRE: Shooter/FPS. Military terms. Quick direct text."
        },
        "plataforma": {
            "name": "Plataforma",
            "context": "GENRE: Platform. Fun light tone. Simple clear instructions."
        },
        "puzzle": {
            "name": "Puzzle",
            "context": "GENRE: Puzzle. Clear hints. Logical precise language."
        },
        "esportes": {
            "name": "Esportes/Corrida",
            "context": "GENRE: Sports/Racing. Brazilian sports terms. Energetic tone."
        },
        "sandbox": {
            "name": "Sandbox/Sobrevivência",
            "context": "GENRE: Sandbox/Survival. Exploration freedom. Crafting terms."
        },
        "metroidvania": {
            "name": "Metroidvania",
            "context": "GENRE: Metroidvania. Exploration hints. Ability descriptions."
        },
        "infantil": {
            "name": "Infantil",
            "context": "GENRE: Children. Simple positive language. Short fun sentences."
        }
    }

    @staticmethod
    def get_system_prompt(style: str = "anos_90", genre: str = "auto") -> str:
        """
        System prompt que define comportamento técnico.

        Args:
            style: Estilo (anos_80, anos_90, anos_2000, moderno, literal)
            genre: Gênero do jogo

        Returns:
            System prompt
        """
        base = "ACT AS A PROFESSIONAL GAME LOCALIZER. Translate to PT-BR."

        # Adiciona estilo
        style_info = ROMTranslationPrompts.STYLES.get(style, ROMTranslationPrompts.STYLES["anos_90"])
        style_addon = style_info["prompt_addon"]

        # Adiciona contexto de gênero
        genre_info = ROMTranslationPrompts.GENRES.get(genre, ROMTranslationPrompts.GENRES["auto"])
        genre_context = genre_info["context"]

        # Regras para nomes de locais/fases
        location_rules = """LOCATION NAMES: Translate descriptively.
KEEP = Fortaleza/Covil, CASTLE = Castelo, WORLD = Mundo, LAND = Terra
Examples: K. ROOL'S KEEP = FORTALEZA DO K. ROOL, LOST WORLD = MUNDO PERDIDO"""

        return f"""{base}
{style_addon}
{genre_context}
{location_rules}
IF INPUT IS GARBAGE OR BINARY, RETURN IT UNCHANGED.
OUTPUT ONLY THE TRANSLATION. NO EXPLANATIONS."""

    # Contextos de texto (menu, diálogo, tutorial, etc)
    CONTEXTS = {
        "menu": {
            "name": "Menu",
            "detect_keywords": ["START", "CONTINUE", "OPTIONS", "EXIT", "SAVE", "LOAD", "NEW GAME", "SETTINGS"],
            "rules": """CONTEXT: Game Menu
- Translate ALL menu items to Portuguese (Iniciar, Continuar, Opções, Sair, Salvar, Carregar)
- Keep translations SHORT (menus have limited space)
- Be DIRECT and CLEAR"""
        },
        "dialog": {
            "name": "Diálogo",
            "detect_keywords": ["?", "!", "...", '"', "said", "asked", "replied"],
            "rules": """CONTEXT: Character Dialogue
- Translate EVERYTHING - do NOT leave English words
- PRESERVE character personality (sarcastic, grumpy, funny, angry)
- Use natural Brazilian Portuguese speech patterns
- Keep the emotional tone intact"""
        },
        "tutorial": {
            "name": "Tutorial",
            "detect_keywords": ["PRESS", "PUSH", "HOLD", "BUTTON", "MOVE", "JUMP", "ATTACK"],
            "rules": """CONTEXT: Tutorial/Instructions
- Translate button names: START=INÍCIO, SELECT=SELECIONAR
- Be CLEAR and DIRECT
- Use imperative form: Pressione, Segure, Mova"""
        },
        "system": {
            "name": "Sistema",
            "detect_keywords": ["GAME OVER", "PAUSE", "SCORE", "LIVES", "TIME", "LEVEL"],
            "rules": """CONTEXT: System Messages
- Translate system terms: Game Over=Fim de Jogo, Pause=Pausado, Score=Pontuação
- Lives=Vidas, Time=Tempo, Level=Fase
- Keep SHORT for display limits"""
        },
        "story": {
            "name": "História",
            "detect_keywords": ["Once upon", "Long ago", "In the", "The kingdom", "princess", "hero"],
            "rules": """CONTEXT: Story/Narrative
- Use flowing narrative Portuguese
- Maintain epic/dramatic tone
- Translate COMPLETELY - no English"""
        }
    }

    @staticmethod
    def detect_context(text: str) -> str:
        """
        Detecta automaticamente o contexto do texto.

        Returns:
            Tipo de contexto: 'menu', 'dialog', 'tutorial', 'system', 'story', ou 'general'
        """
        text_upper = text.upper()

        for context_type, context_info in ROMTranslationPrompts.CONTEXTS.items():
            for keyword in context_info["detect_keywords"]:
                if keyword.upper() in text_upper:
                    return context_type

        # Default: se tem pontuação de diálogo, é diálogo
        if any(p in text for p in ['?', '!', '...', '"']):
            return 'dialog'

        return 'general'

    @staticmethod
    def get_contextual_prompt(text: str, target_language: str = "Portuguese (Brazil)", context: str = None) -> str:
        """
        Gera prompt com regras específicas para o contexto.

        Args:
            text: Texto a traduzir
            target_language: Idioma alvo
            context: Contexto forçado (ou None para auto-detectar)

        Returns:
            Prompt otimizado para o contexto
        """
        # Auto-detecta contexto se não fornecido
        if context is None:
            context = ROMTranslationPrompts.detect_context(text)

        # Pega regras do contexto
        context_info = ROMTranslationPrompts.CONTEXTS.get(context, {})
        context_rules = context_info.get("rules", "")

        return f"""You are a professional video game translator.

{context_rules}

ABSOLUTE RULES:
1. Translate EVERYTHING to {target_language}
2. Do NOT leave ANY English words (except character names like Mario, Link, Kong)
3. PRESERVE control codes: <0A>, {{VAR}}, [NAME]
4. Output ONLY the translation, no explanations

English: {text}
Portuguese:"""

    @staticmethod
    def get_translation_prompt(text: str, target_language: str = "Portuguese (Brazil)") -> str:
        """
        Gera prompt de tradução técnico e determinístico.

        Args:
            text: Texto a traduzir
            target_language: Idioma alvo

        Returns:
            Prompt completo
        """
        return f"""Translate to {target_language}.

RULES:
1. If text is natural language: translate it
2. If text is technical/binary: return it UNCHANGED
3. PRESERVE all control codes: <0A>, {{VAR}}, [NAME]
4. Keep translation length similar to original (max +30%)
5. Return ONLY the translation, no explanations

Text: {text}
Translation:"""

    @staticmethod
    def get_strict_prompt(text: str, target_language: str = "Portuguese (Brazil)", max_length: int = None) -> str:
        """
        Prompt com limite estrito de comprimento (ROM hacking).

        Args:
            text: Texto a traduzir
            target_language: Idioma alvo
            max_length: Comprimento máximo permitido

        Returns:
            Prompt com restrição de comprimento
        """
        length_constraint = ""
        if max_length:
            length_constraint = f"\n5. CRITICAL: Translation MUST be ≤{max_length} characters (original: {len(text)})"

        return f"""Translate to {target_language} for ROM hacking.

RULES:
1. PRESERVE all codes: <0A>, {{VAR}}, [NAME]
2. If not natural language: return UNCHANGED
3. Keep translation SHORTER or equal length to original
4. Use abbreviations if needed to fit{length_constraint}

Text: {text}
Translation (max {max_length or len(text)} chars):"""

    @staticmethod
    def get_batch_prompt(texts: list, target_language: str = "Portuguese (Brazil)") -> str:
        """
        Prompt para tradução em batch.

        Args:
            texts: Lista de textos
            target_language: Idioma alvo

        Returns:
            Prompt de batch
        """
        numbered_texts = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])

        return f"""Translate these {len(texts)} texts to {target_language}.

RULES:
1. Translate ONLY natural language
2. Return technical/binary texts UNCHANGED
3. PRESERVE all control codes
4. Output format: one translation per line, numbered

Texts:
{numbered_texts}

Translations:"""

    @staticmethod
    def extract_translation(response: str, original: str) -> str:
        """
        Extrai tradução de resposta do LLM com fallback robusto.
        COMMERCIAL GRADE: Implements Decapitator, Explanation Remover and Recovery Fallback.

        Args:
            response: Resposta do modelo
            original: Texto original

        Returns:
            Tradução extraída (NUNCA None)
        """
        if response is None or response == "":
            return original  # Fallback 1: resposta vazia

        # Remove prefixos comuns
        response = response.strip()

        # COMMERCIAL GRADE: EXPLANATION REMOVER
        # Remove explicações da IA que vazam na resposta
        explanation_patterns = [
            "In Portuguese,",
            "In Portuguese ",
            "The original",
            "This is a machine translation",
            "This translates to",
            "which means",
            "means ",
            "is the Portuguese",
            "is an informal term",
            "In this context,",
            '"lixo" tr',
            '"Prêmio" means',
            "The translation",
        ]

        for pattern in explanation_patterns:
            if pattern in response:
                # Remove tudo a partir da explicação
                response = response.split(pattern)[0].strip()

        # COMMERCIAL GRADE: MIXED LANGUAGE DETECTOR V2
        # Detecta inglês não traduzido - MAS PERMITE diálogos de personagens traduzidos

        # BYPASS: Se parece diálogo de personagem de jogo, NÃO aplica filtro agressivo
        # Diálogos de Cranky Kong, NPCs, etc podem ter tom sarcástico/informal
        dialog_indicators = [
            # Indicadores de diálogo traduzido (português)
            "Pah", "pah", "Bah", "bah", "Ora", "ora", "Hunf", "hunf",
            "não é", "não pode", "não vai", "não tem", "não era",
            "você", "vocês", "eles", "deles", "dela", "dele",
            "esse", "essa", "esses", "essas", "isto", "isso",
            "como", "quando", "porque", "porquê", "então",
            "meu", "minha", "seus", "suas", "nosso", "nossa",
            "está", "estão", "estava", "eram", "seria", "seriam",
            "fazer", "faz", "fez", "feito", "sendo",
            "aqui", "ali", "lá", "aí", "onde",
            "mais", "menos", "muito", "pouco", "demais",
            "bom", "boa", "mau", "mal", "bem",
            "tempo", "vez", "vezes", "dia", "dias",
            "jogo", "jogar", "jogando", "personagem",
            "herói", "heróis", "heroína", "vilão",
            "macaco", "gorila", "kong", "barril",
            # Pontuação típica de diálogo traduzido
            "!", "?", "...",
        ]

        # Conta indicadores de português no texto
        portuguese_count = sum(1 for indicator in dialog_indicators if indicator.lower() in response.lower())

        # Se tem 3+ indicadores de português, É uma tradução válida - não filtra
        if portuguese_count >= 3:
            pass  # Bypass do filtro de inglês - é diálogo traduzido
        else:
            # Aplica filtro de inglês apenas se NÃO parece diálogo traduzido
            english_indicators = [
                # Padrões estruturais de inglês (apenas os mais óbvios)
                ">YOU ", ">THE ", ">YOUR ", ">WELCOME",
                "You're ", "You'll ", "You've ", "You are ",
                "I'm ", "I'll ", "I've ", "I am ", "I don't ", "I can't ", "I won't ",
                "He's ", "He'll ", "He is ", "She's ", "She'll ", "She is ",
                "It's ", "It is ", "It'll ",
                "We're ", "We'll ", "We've ", "We are ",
                "They're ", "They'll ", "They've ", "They are ",
                "Don't ", "Doesn't ", "Didn't ", "Won't ", "Wouldn't ", "Couldn't ", "Shouldn't ",
                "Can't ", "Cannot ", "Isn't ", "Aren't ", "Wasn't ", "Weren't ",
                "What's ", "That's ", "There's ", "Here's ",
            ]

            # Conta quantos indicadores de inglês estão presentes
            english_count = sum(1 for indicator in english_indicators if indicator in response)

            # Se tem 3+ indicadores de inglês E poucos de português, não foi traduzido
            if english_count >= 3 and portuguese_count < 2:
                return original  # Texto não traduzido detectado

            # Verificação de proporção apenas para textos longos sem indicadores de português
            if portuguese_count < 2:
                common_english_words = {'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                                        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                                        'could', 'should', 'may', 'might', 'must', 'shall',
                                        'this', 'that', 'these', 'those', 'with', 'from', 'into',
                                        'your', 'their', 'his', 'her', 'its', 'our', 'my',
                                        'and', 'but', 'for', 'not', 'you', 'all', 'can'}

                words = response.lower().split()
                if len(words) >= 6:
                    english_word_count = sum(1 for w in words if w.strip('.,!?"\'-') in common_english_words)
                    english_ratio = english_word_count / len(words)
                    # Aumentado threshold: só rejeita se >40% inglês E sem português
                    if english_ratio > 0.40:
                        return original

        # COMMERCIAL GRADE: WRONG LANGUAGE DETECTOR
        # Detecta se Mistral traduziu para idioma errado (francês, espanhol, etc)
        wrong_language_indicators = [
            # Francês
            "C'est ", "c'est ", "d~plorable", "n'est ", "qu'il ", "l'", "j'ai ",
            "Je suis ", "Vous êtes ", "Il est ", "Elle est ", "Nous sommes ",
            " le ", " la ", " les ", " un ", " une ", " des ", " du ", " de la ",
            " est ", " sont ", " avec ", " pour ", " dans ", " sur ", " sous ",
            "Bonjour", "Merci", "S'il vous plaît",
            # Espanhol
            "¿", "¡", " el ", " ella ", " ellos ", " usted ",
            "Hola ", "Gracias ", "Por favor ",
            " está ", " están ", " es ", " son ",
            # Italiano
            " il ", " lo ", " gli ", " i ",
            "Ciao ", "Grazie ", "Per favore ",
            # Alemão
            " der ", " die ", " das ", " ein ", " eine ",
            "Guten ", "Danke ", "Bitte ",
        ]

        for indicator in wrong_language_indicators:
            if indicator in response:
                return original  # Idioma errado detectado

        # COMMERCIAL GRADE: DECAPITATOR V2
        # Remove prefixos de IA e mantém diálogos de personagens
        game_characters = [
            'Cranky', 'Diddy', 'Dixie', 'Funky', 'Wrinkly', 'Donkey',
            'Mario', 'Luigi', 'Peach', 'Bowser', 'Toad',
            'Link', 'Zelda', 'Ganon', 'Navi',
            'Sonic', 'Tails', 'Knuckles', 'Eggman',
        ]
        if ':' in response:
            if not any(name in response for name in game_characters):
                parts = response.split(':', 1)
                # Só aplica se a parte antes for curta (provavelmente prefixo)
                if len(parts[0]) < 25:
                    response = parts[1].strip()

        # COMMERCIAL GRADE: RECOVERY FALLBACK
        # If response contains AI chatter keywords anywhere, return ORIGINAL
        # NOTA: Apenas padrões INEQUÍVOCOS de "AI chatter" - não bloquear diálogos de jogo
        chatter_keywords = [
            "As an AI", "As a language model", "As an artificial",
            "I was trained", "My purpose is", "I don't have the ability",
            "Como uma IA", "Como um modelo de linguagem", "Não tenho capacidade de",
            "I cannot translate", "I apologize for", "I'm sorry, but",
            "Here is the translation:", "The translation is:",
            "Let me translate", "I'll translate",
        ]

        for keyword in chatter_keywords:
            # Match exato para evitar falsos positivos em diálogos de jogo
            if keyword.lower() in response.lower():
                # Bypass se tem indicadores de português (é diálogo traduzido, não AI chatter)
                if portuguese_count >= 2:
                    continue  # Ignora este keyword, é diálogo válido
                return original  # Recovery Fallback: AI chatter detected

        # Remove "Translation: " ou similar
        prefixes = [
            "Translation", "Tradução", "Output", "Result", "Answer",
            "Portuguese", "PT-BR", "Brazilian",
        ]

        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].lstrip(':').strip()

        # COMMERCIAL GRADE: Strip ALL quotes (" and ')
        response = response.strip('"').strip("'")

        # Se resposta virou vazia após limpeza
        if not response:
            return original  # Fallback 2: limpeza removeu tudo

        # IMPROVED: Extração inteligente de tradução multi-linha
        # Pega a linha mais relevante (não a primeira cegamente)
        lines = [l.strip() for l in response.split('\n') if l.strip()]
        if len(lines) > 1:
            # Filtra linhas que parecem explicações
            valid_lines = []
            for line in lines:
                # Ignora linhas que começam com padrões de explicação
                skip_patterns = [
                    'Note:', 'Nota:', '(', '*', '-', '#',
                    'This ', 'The ', 'In ', 'Here ',
                ]
                if not any(line.startswith(p) for p in skip_patterns):
                    valid_lines.append(line)

            if valid_lines:
                # Pega a primeira linha válida
                response = valid_lines[0]
            else:
                response = lines[0]
        elif lines:
            response = lines[0]

        # FINAL CHECK: Se resposta é muito curta comparado ao original
        if len(response) < len(original) * 0.3 and len(original) > 10:
            return original  # Tradução muito curta, provavelmente truncada

        return response if response else original  # Fallback final

    @staticmethod
    def validate_and_fix_translation(original: str, translation: str) -> str:
        """
        Valida tradução e corrige problemas comuns.

        Args:
            original: Texto original
            translation: Tradução

        Returns:
            Tradução validada/corrigida (NUNCA None)
        """
        if translation is None or translation == "":
            return original  # Nunca retorna None

        # Preserva códigos de controle se faltarem
        control_codes = [
            '<0A>', '<0D>', '<00>', '<FF>',
            '{VAR}', '{PLAYER}', '{ITEM}', '{NAME}',
            '[NAME]', '[PAUSE]', '[WAIT]', '[END]'
        ]

        for code in control_codes:
            original_count = original.count(code)
            translation_count = translation.count(code)

            # Se código foi removido, adiciona de volta
            if original_count > translation_count:
                missing = original_count - translation_count
                translation += (code * missing)

        # Trunca se ficou muito longo (ROM hacking)
        max_safe_length = int(len(original) * 1.5)
        if len(translation) > max_safe_length:
            translation = translation[:len(original)]

        return translation


def main():
    """CLI para testar prompts."""
    prompts = ROMTranslationPrompts()

    print("=" * 60)
    print("ROM TRANSLATION PROMPTS - EXEMPLOS")
    print("=" * 60)

    test_cases = [
        "Hello {PLAYER}!",
        "<0A><0D><FF>",
        "Press START",
        "0x1234",
        "Game Over"
    ]

    print("\n1. SYSTEM PROMPT:")
    print("-" * 60)
    print(prompts.get_system_prompt())

    print("\n2. TRANSLATION PROMPTS:")
    print("-" * 60)
    for text in test_cases:
        prompt = prompts.get_translation_prompt(text, "Portuguese (Brazil)")
        print(f"\nText: {text}")
        print(f"Prompt:\n{prompt}\n")

    print("\n3. STRICT PROMPT (ROM hacking):")
    print("-" * 60)
    strict = prompts.get_strict_prompt("New Game", "Portuguese (Brazil)", max_length=8)
    print(strict)

    print("\n4. EXTRACTION TEST:")
    print("-" * 60)
    test_responses = [
        ('Translation: Olá mundo', 'Hello world'),
        ('"Pressione START"', 'Press START'),
        ('I cannot translate this', 'Binary data'),
        ('', 'Empty'),
        (None, 'None response'),
    ]

    for response, original in test_responses:
        extracted = prompts.extract_translation(response, original)
        print(f"Response: {response}")
        print(f"Original: {original}")
        print(f"Extracted: {extracted}")
        print(f"Type: {type(extracted)}")
        print()

    print("=" * 60)


if __name__ == '__main__':
    main()
