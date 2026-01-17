# 📚 Guia de Integração de Glossários

## ✅ Sistema Implementado

O **GlossaryManager** já está funcionando! Aqui está como integrar com cada engine de tradução.

---

## 🎯 Como Funciona

### 1. **Pré-Tradução** (Proteção de Termos)
```python
from core.glossary_manager import get_glossary_manager

gm = get_glossary_manager()

# Protege termos técnicos antes de enviar para a IA
text = "Auto (Gemini → Ollama) mode uses target output"
protected_text, placeholders = gm.apply_pre_translation(text, "en_to_pt")

# protected_text agora tem: "__GLOSSARY_TERM_0__ mode uses __GLOSSARY_TERM_1__"
```

### 2. **Tradução com Contexto**
```python
# Gera prompt com glossário
context = gm.generate_context_prompt("en_to_pt")

# Adiciona ao prompt de tradução
full_prompt = f"""
Traduza o texto abaixo para português do Brasil.

{context}

TEXTO A TRADUZIR:
{protected_text}
"""
```

### 3. **Pós-Tradução** (Substituição)
```python
# Após receber a tradução da IA
translated = ai_translate(full_prompt)

# Substitui placeholders pelos termos corretos
final_text = gm.apply_post_translation(translated, placeholders)
```

---

## 🔧 Integração com Gemini (Google API)

**Arquivo**: `core/gemini_translator.py`

**Localização**: Função `translate_with_gemini()`, linha ~76

**ANTES:**
```python
prompt = f"""
Traduza totalmente o texto abaixo para português do Brasil.
Preserve nomes próprios, formatação, quebras de linha e estilo.

TEXTO A TRADUZIR:
{original_text}
"""
```

**DEPOIS (COM GLOSSÁRIO):**
```python
from core.glossary_manager import get_glossary_manager

# Carrega glossário
gm = get_glossary_manager()

# Protege termos técnicos
protected_text, placeholders = gm.apply_pre_translation(original_text, "en_to_pt")

# Gera contexto do glossário
glossary_context = gm.generate_context_prompt("en_to_pt")

# Novo prompt com glossário
prompt = f"""
Traduza totalmente o texto abaixo para português do Brasil.
Preserve nomes próprios, formatação, quebras de linha e estilo.

{glossary_context}

TEXTO A TRADUZIR:
{protected_text}
"""

# ... (Gemini traduz) ...

# Após receber a tradução
translated_output = gm.apply_post_translation(translated_text, placeholders)
```

---

## 🦙 Integração com Ollama (Llama/Mistral)

**Arquivo**: `core/hybrid_translator.py` ou onde Ollama é chamado

**Mesmo processo do Gemini:**

```python
from core.glossary_manager import get_glossary_manager

def translate_with_ollama(text, model="llama3.2"):
    gm = get_glossary_manager()

    # Pré-tradução
    protected, placeholders = gm.apply_pre_translation(text, "en_to_pt")

    # Prompt com glossário
    glossary = gm.generate_context_prompt("en_to_pt")
    prompt = f"""
    Traduza para português do Brasil.

    {glossary}

    TEXTO:
    {protected}
    """

    # Chama Ollama
    result = ollama.generate(model=model, prompt=prompt)

    # Pós-tradução
    final = gm.apply_post_translation(result, placeholders)
    return final
```

---

## 🌐 Integração com DeepL

**Observação**: DeepL tem glossários nativos via API.

**Opção 1: Usar Glossário Nativo DeepL** (Recomendado)
```python
import deepl

translator = deepl.Translator("YOUR_API_KEY")

# Cria glossário no DeepL
glossary = translator.create_glossary(
    "Glossário Técnico PT-BR",
    source_lang="EN",
    target_lang="PT-BR",
    entries={
        "Auto (Gemini → Ollama)": "Automático (Gemini → Ollama)",
        "target output": "saída desejada",
        # ... mais termos
    }
)

# Usa na tradução
result = translator.translate_text(
    text,
    source_lang="EN",
    target_lang="PT-BR",
    glossary=glossary
)
```

**Opção 2: Usar GlossaryManager** (Pós-processamento)
```python
from core.glossary_manager import get_glossary_manager

gm = get_glossary_manager()

# DeepL traduz normalmente
result = translator.translate_text(text, target_lang="PT-BR")

# Pós-processa com nosso glossário (força termos corretos)
_, placeholders = gm.apply_pre_translation(text, "en_to_pt")
final = gm.apply_post_translation(result.text, placeholders)
```

---

## 🔄 Integração com Modo AUTO (Híbrido)

**Arquivo**: Onde o modo AUTO é implementado

```python
from core.glossary_manager import get_glossary_manager

def auto_translate(text):
    gm = get_glossary_manager()

    # Pré-processamento ÚNICO (aplica uma vez)
    protected, placeholders = gm.apply_pre_translation(text, "en_to_pt")
    glossary_context = gm.generate_context_prompt("en_to_pt")

    # Tenta Gemini primeiro
    try:
        translated = translate_with_gemini(protected, glossary_context)
    except:
        # Fallback para Ollama
        translated = translate_with_ollama(protected, glossary_context)

    # Pós-processamento ÚNICO
    final = gm.apply_post_translation(translated, placeholders)
    return final
```

---

## ✏️ Como Editar o Glossário

### Método 1: Editar o JSON Diretamente
```bash
# Abra o arquivo
notepad config/translation_glossary.json

# Adicione novos termos em "glossary" > "en_to_pt"
{
  "glossary": {
    "en_to_pt": {
      "novo termo": "nova tradução",
      "API endpoint": "ponto de acesso da API"
    }
  }
}
```

### Método 2: Via Código Python
```python
from core.glossary_manager import get_glossary_manager

gm = get_glossary_manager()

# Adiciona termo
gm.add_term("API endpoint", "ponto de acesso da API", "en_to_pt", save=True)

# Remove termo
gm.remove_term("old term", "en_to_pt", save=True)

# Ver estatísticas
print(gm.get_stats())
```

### Método 3: Interface Gráfica (TODO)
```python
# Futura feature: botão "Editar Glossário" na GUI
# Permitirá editar termos sem sair do programa
```

---

## 📊 Estatísticas do Glossário Atual

```
Total de pares de idiomas: 3
  • en_to_pt (Inglês → Português): 26 termos
  • ja_to_pt (Japonês → Português): 7 termos
  • proper_nouns (Nomes Próprios): 10 termos

Total de termos técnicos: 43
```

---

## 🧪 Testes

### Teste Rápido
```bash
cd core
python glossary_manager.py
```

### Teste de Integração
```python
from core.glossary_manager import get_glossary_manager

gm = get_glossary_manager()

# Texto de teste
text = """
The Auto (Gemini → Ollama) mode uses Online Gemini (Google API)
for target output with BPP format and offset detection.
"""

# Aplica glossário
protected, placeholders = gm.apply_pre_translation(text)
final = gm.apply_post_translation(protected, placeholders)

print("Antes:", text)
print("Depois:", final)
```

**Resultado Esperado:**
```
Antes: The Auto (Gemini → Ollama) mode uses...
Depois: The Automático (Gemini → Ollama) mode uses Gemini Online (API do Google)...
```

---

## ⚙️ Configuração Avançada

### Glossários por Jogo
```python
# Crie glossários específicos para cada jogo
gm_final_fantasy = GlossaryManager("config/glossary_final_fantasy.json")
gm_zelda = GlossaryManager("config/glossary_zelda.json")

# Use o glossário apropriado
if game == "Final Fantasy":
    translated = translate_with_glossary(text, gm_final_fantasy)
elif game == "Zelda":
    translated = translate_with_glossary(text, gm_zelda)
```

### Detecção Automática de Idioma
```python
# Detecta se o texto é japonês ou inglês
import langdetect

detected_lang = langdetect.detect(text)

if detected_lang == "ja":
    pair = "ja_to_pt"
elif detected_lang == "en":
    pair = "en_to_pt"

protected, placeholders = gm.apply_pre_translation(text, pair)
```

---

## 🚀 Próximos Passos

1. **Integrar com `gemini_translator.py`** ✅ (código fornecido acima)
2. **Integrar com `hybrid_translator.py`** (Ollama/Llama/Mistral)
3. **Adicionar botão "Editar Glossário" na GUI** (futuro)
4. **Criar glossários específicos por console** (SNES, PS1, etc.)
5. **Importar/Exportar glossários** (.csv, .xlsx)

---

## 📝 Exemplo Completo de Uso

```python
#!/usr/bin/env python3
from core.glossary_manager import get_glossary_manager

def translate_rom_text(original_text: str, source_lang: str = "en") -> str:
    """
    Traduz texto de ROM usando glossário personalizado.

    Args:
        original_text: Texto original do jogo
        source_lang: Idioma de origem ("en", "ja", etc.)

    Returns:
        Texto traduzido com termos técnicos corretos
    """
    # Carrega glossário
    gm = get_glossary_manager()

    # Determina par de idiomas
    language_pair = f"{source_lang}_to_pt"

    # Pré-tradução: protege termos
    protected_text, placeholders = gm.apply_pre_translation(
        original_text,
        language_pair
    )

    # Contexto do glossário para a IA
    glossary_context = gm.generate_context_prompt(language_pair)

    # Monta prompt completo
    prompt = f"""
    Traduza o texto abaixo para português do Brasil.
    Mantenha o estilo de jogos retrô.

    {glossary_context}

    TEXTO:
    {protected_text}
    """

    # Envia para IA (Gemini/Ollama/DeepL)
    translated_raw = your_ai_function(prompt)

    # Pós-tradução: substitui placeholders
    final_translation = gm.apply_post_translation(
        translated_raw,
        placeholders
    )

    return final_translation

# Uso
if __name__ == "__main__":
    test_text = "Auto (Gemini → Ollama) mode with target output"
    result = translate_rom_text(test_text, source_lang="en")
    print(f"Tradução: {result}")
```

---

## ✅ Checklist de Implementação

- [x] Criar `translation_glossary.json`
- [x] Criar `glossary_manager.py`
- [x] Testar pré e pós-tradução
- [ ] Integrar com Gemini
- [ ] Integrar com Ollama
- [ ] Integrar com DeepL
- [ ] Integrar com modo AUTO
- [ ] Adicionar UI para editar glossário
- [ ] Criar glossários por console
- [ ] Documentar para usuários finais

---

## 🎓 Conclusão

O sistema de glossários está **100% funcional** e pronto para ser integrado!

**Benefícios:**
- ✅ Traduções técnicas precisas
- ✅ Termos consistentes em todos os textos
- ✅ Fácil de editar (JSON simples)
- ✅ Compatível com todas as engines (Gemini, Ollama, DeepL)
- ✅ Suporta múltiplos idiomas

**Edite o glossário em**: `config/translation_glossary.json`

**Código fonte em**: `core/glossary_manager.py`

---

**Autor**: ROM Translation Framework Team
**Versão**: 1.0.0
**Data**: 2025-12-28
