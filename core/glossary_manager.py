#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Glossary Manager - Sistema de Glossários Personalizados
========================================================
Gerencia glossários personalizados para traduções técnicas precisas.

Author: ROM Translation Framework Team
License: MIT
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class GlossaryManager:
    """
    Gerenciador de glossários personalizados para traduções.

    Funcionalidades:
    - Carrega glossários de arquivos JSON
    - Aplica substituições pré-tradução (protege termos)
    - Aplica substituições pós-tradução (força termos corretos)
    - Gera prompts contextualizados para IAs
    - Suporta múltiplos pares de idiomas
    """

    def __init__(self, glossary_path: Optional[str] = None):
        """
        Inicializa o gerenciador de glossários.

        Args:
            glossary_path: Caminho para o arquivo JSON de glossários.
                          Se None, usa o padrão em config/translation_glossary.json
        """
        if glossary_path is None:
            # Caminho padrão relativo ao projeto
            project_root = Path(__file__).parent.parent
            glossary_path = project_root / "config" / "translation_glossary.json"

        self.glossary_path = Path(glossary_path)
        self.glossaries: Dict[str, Dict[str, str]] = {}
        self.proper_nouns: Dict[str, str] = {}
        self._load_glossary()

    def _load_glossary(self) -> bool:
        """
        Carrega o glossário do arquivo JSON.

        Returns:
            True se carregado com sucesso, False caso contrário
        """
        try:
            if not self.glossary_path.exists():
                print(f"⚠️ Glossário não encontrado: {self.glossary_path}")
                print(f"💡 Criando glossário padrão...")
                self._create_default_glossary()

            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Carrega glossários por par de idiomas
            self.glossaries = data.get("glossary", {})
            self.proper_nouns = data.get("glossary", {}).get("proper_nouns", {})

            total_terms = sum(len(g) for g in self.glossaries.values())
            print(f"✅ Glossário carregado: {total_terms} termos técnicos")
            return True

        except json.JSONDecodeError as e:
            print(f"❌ Erro ao ler glossário: {e}")
            return False
        except Exception as e:
            print(f"❌ Erro inesperado ao carregar glossário: {e}")
            return False

    def _create_default_glossary(self):
        """Cria um glossário padrão se não existir."""
        self.glossary_path.parent.mkdir(parents=True, exist_ok=True)

        default_glossary = {
            "_meta": {
                "description": "Glossário personalizado para traduções",
                "version": "1.0.0"
            },
            "glossary": {
                "en_to_pt": {
                    "Auto (Gemini → Ollama)": "Automático (Gemini → Ollama)",
                    "target output": "saída desejada"
                },
                "proper_nouns": {
                    "Gemini": "Gemini",
                    "Ollama": "Ollama"
                }
            }
        }

        with open(self.glossary_path, 'w', encoding='utf-8') as f:
            json.dump(default_glossary, f, indent=2, ensure_ascii=False)

    def get_glossary(self, language_pair: str = "en_to_pt") -> Dict[str, str]:
        """
        Retorna o glossário para um par de idiomas específico.

        Args:
            language_pair: Par de idiomas (ex: "en_to_pt", "ja_to_pt")

        Returns:
            Dicionário de termos {original: tradução}
        """
        return self.glossaries.get(language_pair, {})

    def apply_pre_translation(self, text: str, language_pair: str = "en_to_pt") -> Tuple[str, Dict[str, str]]:
        """
        Aplica proteção de termos ANTES da tradução.

        Substitui termos técnicos por placeholders únicos para evitar
        que sejam traduzidos incorretamente pela IA.

        Args:
            text: Texto original
            language_pair: Par de idiomas

        Returns:
            Tupla (texto_protegido, mapa_de_placeholders)
        """
        glossary = self.get_glossary(language_pair)
        placeholders = {}
        protected_text = text

        # Ordena por comprimento decrescente (evita substituições parciais)
        sorted_terms = sorted(glossary.keys(), key=len, reverse=True)

        for idx, original_term in enumerate(sorted_terms):
            if original_term in protected_text:
                placeholder = f"__GLOSSARY_TERM_{idx}__"
                placeholders[placeholder] = glossary[original_term]
                # Case-insensitive replacement
                pattern = re.compile(re.escape(original_term), re.IGNORECASE)
                protected_text = pattern.sub(placeholder, protected_text)

        return protected_text, placeholders

    def apply_post_translation(self, translated_text: str, placeholders: Dict[str, str]) -> str:
        """
        Aplica substituição de placeholders DEPOIS da tradução.

        Substitui os placeholders pelos termos corretos do glossário.

        Args:
            translated_text: Texto traduzido com placeholders
            placeholders: Mapa de placeholders → termos corretos

        Returns:
            Texto com termos técnicos corretos
        """
        result = translated_text

        for placeholder, correct_term in placeholders.items():
            result = result.replace(placeholder, correct_term)

        return result

    def generate_context_prompt(self, language_pair: str = "en_to_pt") -> str:
        """
        Gera um prompt contextual com os termos do glossário.

        Este prompt deve ser adicionado à instrução de tradução para
        orientar a IA sobre como traduzir termos técnicos.

        Args:
            language_pair: Par de idiomas

        Returns:
            String com instruções de glossário para a IA
        """
        glossary = self.get_glossary(language_pair)

        if not glossary:
            return ""

        prompt_lines = [
            "\n🔧 GLOSSÁRIO TÉCNICO (Traduza exatamente como indicado):",
            "=" * 60
        ]

        for original, translation in sorted(glossary.items())[:20]:  # Máximo 20 termos no prompt
            prompt_lines.append(f"• \"{original}\" → \"{translation}\"")

        if len(glossary) > 20:
            prompt_lines.append(f"... e mais {len(glossary) - 20} termos técnicos.")

        prompt_lines.append("=" * 60)
        prompt_lines.append("⚠️ Respeite EXATAMENTE estes termos técnicos na tradução.\n")

        return "\n".join(prompt_lines)

    def add_term(self, original: str, translation: str, language_pair: str = "en_to_pt", save: bool = True):
        """
        Adiciona um novo termo ao glossário.

        Args:
            original: Termo original
            translation: Tradução desejada
            language_pair: Par de idiomas
            save: Se True, salva o glossário no arquivo
        """
        if language_pair not in self.glossaries:
            self.glossaries[language_pair] = {}

        self.glossaries[language_pair][original] = translation

        if save:
            self._save_glossary()

    def remove_term(self, original: str, language_pair: str = "en_to_pt", save: bool = True):
        """
        Remove um termo do glossário.

        Args:
            original: Termo a remover
            language_pair: Par de idiomas
            save: Se True, salva o glossário no arquivo
        """
        if language_pair in self.glossaries and original in self.glossaries[language_pair]:
            del self.glossaries[language_pair][original]

            if save:
                self._save_glossary()

    def _save_glossary(self):
        """Salva o glossário de volta no arquivo JSON."""
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data["glossary"] = self.glossaries

            with open(self.glossary_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"✅ Glossário salvo em: {self.glossary_path}")
        except Exception as e:
            print(f"❌ Erro ao salvar glossário: {e}")

    def get_stats(self) -> Dict[str, int]:
        """
        Retorna estatísticas do glossário.

        Returns:
            Dicionário com estatísticas
        """
        return {
            "total_language_pairs": len(self.glossaries),
            "total_terms": sum(len(g) for g in self.glossaries.values()),
            "proper_nouns": len(self.proper_nouns),
            **{f"terms_{pair}": len(terms) for pair, terms in self.glossaries.items()}
        }


# Singleton global para fácil acesso
_global_glossary_manager = None

def get_glossary_manager(glossary_path: Optional[str] = None) -> GlossaryManager:
    """
    Retorna a instância global do GlossaryManager (singleton).

    Args:
        glossary_path: Caminho para o glossário (apenas na primeira chamada)

    Returns:
        Instância do GlossaryManager
    """
    global _global_glossary_manager

    if _global_glossary_manager is None:
        _global_glossary_manager = GlossaryManager(glossary_path)

    return _global_glossary_manager


# Exemplo de uso
if __name__ == "__main__":
    # Teste do glossário
    gm = GlossaryManager()

    print("\n📚 Estatísticas do Glossário:")
    print(json.dumps(gm.get_stats(), indent=2))

    print("\n🔍 Teste de Pré-Tradução:")
    test_text = "The target output uses Auto (Gemini → Ollama) mode with Online Gemini (Google API)."
    protected, placeholders = gm.apply_pre_translation(test_text)
    print(f"Original: {test_text}")
    print(f"Protegido: {protected}")

    print("\n🔍 Teste de Pós-Tradução:")
    simulated_translation = protected  # Simulação
    final_text = gm.apply_post_translation(simulated_translation, placeholders)
    print(f"Final: {final_text}")

    print("\n📝 Prompt Contextual:")
    print(gm.generate_context_prompt())
