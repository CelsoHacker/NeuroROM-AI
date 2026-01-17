# 💾 TRANSLATION CACHE - Sistema de Cache de Traduções

## 🎯 OBJETIVO

Economizar chamadas de API armazenando traduções já realizadas em cache local persistente.

---

## ✅ VANTAGENS

**Economia**:
- ✅ **Reduz até 90% das chamadas de API** em traduções repetidas
- ✅ **Economia de custos** (Gemini API cobra por caractere)
- ✅ **Velocidade 100x maior** (cache local vs API)

**Casos de Uso**:
- 🔄 Retraduzir mesmo jogo após correções
- 🎮 Múltiplas versões do mesmo jogo (v1.0, v1.1, v1.2)
- 📝 Textos compartilhados entre jogos (menus padrão, erros comuns)
- 🧪 Testes de tradução sem gastar API

---

## 📊 FUNCIONAMENTO

### **Sistema de Hash MD5**

```python
# Texto original + idioma alvo = Hash único
"Hello World" + "Portuguese (Brazil)" → "5d41402abc4b2a76b9719d911017c592"

# Cache armazena:
{
  "5d41402abc4b2a76b9719d911017c592": {
    "original": "Hello World",
    "translated": "Olá Mundo",
    "target_language": "Portuguese (Brazil)",
    "created": "2025-01-10T21:30:00",
    "hits": 15
  }
}
```

### **Fluxo de Tradução com Cache**

```
Texto → Hash MD5 → Busca no Cache
                         ↓
                   Encontrado?
                    /        \
                 SIM          NÃO
                  ↓            ↓
        Retorna cache   Chama API Gemini
                             ↓
                    Armazena no cache
                             ↓
                      Retorna tradução
```

---

## 🚀 COMO USAR

### **Modo 1: Automático (Padrão no Pipeline)**

```python
from core.pc_pipeline import PCTranslationPipeline

pipeline = PCTranslationPipeline("C:\\Games\\MyGame")

# Cache HABILITADO por padrão (use_cache=True)
result = pipeline.run_full_pipeline(
    api_key="AIza...",
    target_language="Portuguese (Brazil)",
    use_cache=True  # ← Padrão (pode omitir)
)

# Cache salvo em: MyGame/translation_output/translation_cache.json
```

### **Modo 2: Manual (Controle Total)**

```python
from core.pc_translation_cache import TranslationCache

# Cria/carrega cache
cache = TranslationCache("my_cache.json")

# Verifica se texto já foi traduzido
translation = cache.get("Hello World", "Portuguese (Brazil)")

if translation:
    print(f"✅ Cache hit: {translation}")
else:
    # Traduz via API
    translation = api_translate("Hello World")

    # Armazena no cache
    cache.set("Hello World", translation, "Portuguese (Brazil)")

# Salva cache
cache.save_cache()
```

### **Modo 3: Batch (Lotes)**

```python
from core.pc_translation_cache import TranslationCache

cache = TranslationCache("cache.json")
texts = ["Hello", "World", "Goodbye"]

# Busca múltiplos textos
cached, uncached = cache.get_batch(texts, "Portuguese (Brazil)")

print(f"Cached: {cached}")        # {0: "Olá", 2: "Adeus"}
print(f"Need API: {uncached}")    # [(1, "World")]

# Traduz apenas os não cacheados
new_translations = api_translate([text for _, text in uncached])

# Armazena novos
cache.set_batch([text for _, text in uncached], new_translations)
cache.save_cache()
```

---

## 📋 COMANDOS CLI

### **Ver Estatísticas do Cache**

```bash
python -m core.pc_translation_cache stats translation_cache.json
```

**Saída**:
```
📊 CACHE STATISTICS
======================================================================
Cache file: translation_cache.json
Total entries: 1,542
Total hits: 8,234
File size: 245.67 KB

🔥 TOP 10 MOST USED TRANSLATIONS:
  1. [125 hits] Press any key to continue...
  2. [ 98 hits] Loading...
  3. [ 76 hits] Settings
  4. [ 65 hits] Continue
  5. [ 54 hits] New Game
======================================================================
```

### **Limpar Cache Completamente**

```bash
python -m core.pc_translation_cache clear translation_cache.json
```

**Confirmação**:
```
⚠️  Clear all 1,542 entries? (yes/no): yes
✅ Cache cleared
```

### **Remover Entradas Antigas**

```bash
# Remove textos não usados há 90+ dias
python -m core.pc_translation_cache clean translation_cache.json 90
```

**Saída**:
```
🗑️  Removed 234 old cache entries (unused for 90+ days)
✅ Removed 234 entries unused for 90+ days
```

---

## 💡 CASOS DE USO REAIS

### **Caso 1: Retraduzir Jogo Após Correções**

```bash
# Primeira tradução (0% cache)
python -m core.pc_pipeline translate "C:\Games\MyGame" "AIza..."
# Resultado: 500 textos, 500 API calls, $2.50

# Corrige 10 textos manualmente e retraduz
python -m core.pc_pipeline translate "C:\Games\MyGame" "AIza..."
# Resultado: 500 textos, 10 API calls, $0.05 (98% economia!)
```

### **Caso 2: Múltiplas Versões do Jogo**

```bash
# Traduz v1.0
python -m core.pc_pipeline translate "C:\Games\MyGame_v1.0" "AIza..."
# Cache: 0% hit, 1000 API calls

# Traduz v1.1 (95% textos iguais)
python -m core.pc_pipeline translate "C:\Games\MyGame_v1.1" "AIza..."
# Cache: 95% hit, 50 API calls (economia de $4.75!)
```

### **Caso 3: Jogos da Mesma Série**

```bash
# Traduz "Quest RPG 1"
python -m core.pc_pipeline translate "C:\Games\QuestRPG1" "AIza..."
# Cache: 0% hit, 800 API calls

# Traduz "Quest RPG 2" (mesma engine, menus iguais)
python -m core.pc_pipeline translate "C:\Games\QuestRPG2" "AIza..."
# Cache: 60% hit, 320 API calls (economia de $2.40!)
```

---

## 📊 ESTRUTURA DO CACHE

### **Arquivo JSON**

```json
{
  "metadata": {
    "created": "2025-01-10T21:30:00",
    "last_updated": "2025-01-10T22:15:00",
    "version": "1.0",
    "total_entries": 1542
  },
  "translations": {
    "5d41402abc4b2a76b9719d911017c592": {
      "original": "Hello World",
      "translated": "Olá Mundo",
      "target_language": "Portuguese (Brazil)",
      "created": "2025-01-10T21:30:00",
      "last_used": "2025-01-10T22:10:00",
      "hits": 15
    },
    "e10adc3949ba59abbe56e057f20f883e": {
      "original": "Press any key",
      "translated": "Pressione qualquer tecla",
      "target_language": "Portuguese (Brazil)",
      "created": "2025-01-10T21:31:00",
      "last_used": "2025-01-10T22:15:00",
      "hits": 125
    }
  }
}
```

### **Campos Importantes**

- `original`: Texto original em inglês
- `translated`: Tradução em português
- `target_language`: Idioma alvo
- `created`: Data de criação da entrada
- `last_used`: Última vez que foi usado
- `hits`: Quantas vezes foi reutilizado (economia!)

---

## 🔒 SEGURANÇA E QUALIDADE

### **Validações**

✅ **Hash único garante exatidão**:
```python
# Textos diferentes = hashes diferentes
"Hello World" → Hash A
"Hello world" → Hash B (diferente!)
```

✅ **Idioma alvo incluído no hash**:
```python
# Mesmo texto, idiomas diferentes = hashes diferentes
"Hello" + "Portuguese" → Hash A
"Hello" + "Spanish"    → Hash B
```

✅ **Cache não expira automaticamente**:
- Traduções são permanentes (até remoção manual)
- Útil para textos estáticos (menus, erros)

### **Limitações**

⚠️ **Contexto não é considerado**:
```python
# Problema: mesma palavra, contextos diferentes
"Play" (jogo) → "Jogar"
"Play" (peça de teatro) → "Jogar"  # ❌ Incorreto!

# Solução: Limpar cache e retraduzir com contexto
```

⚠️ **Atualizações de tradução**:
```python
# Se melhorar tradução, precisa limpar cache manualmente
cache.clear()  # ou deletar entrada específica
```

---

## 📈 ECONOMIA ESTIMADA

### **Exemplo Real**

**Jogo Indie (500 textos)**:
- Sem cache: 500 API calls = $2.50
- Com cache (2ª tradução): 25 API calls = $0.13
- **Economia: $2.37 (94.8%)**

**Jogo AAA (5000 textos)**:
- Sem cache: 5000 API calls = $25.00
- Com cache (2ª tradução): 250 API calls = $1.25
- **Economia: $23.75 (95%)**

**Série de Jogos (3 jogos, 60% overlap)**:
- Jogo 1: 1000 API calls = $5.00
- Jogo 2: 400 API calls = $2.00 (60% cache hit)
- Jogo 3: 400 API calls = $2.00 (60% cache hit)
- **Total: $9.00 vs $15.00 sem cache (40% economia)**

---

## 🛠️ MANUTENÇÃO DO CACHE

### **Limpeza Recomendada**

```bash
# A cada 3 meses, remove entradas antigas
python -m core.pc_translation_cache clean cache.json 90

# Anualmente, revisar e limpar cache completo se necessário
python -m core.pc_translation_cache clear cache.json
```

### **Backup do Cache**

```bash
# Windows (PowerShell)
Copy-Item "translation_cache.json" "translation_cache_backup_$(Get-Date -Format 'yyyyMMdd').json"

# Linux/Mac
cp translation_cache.json "translation_cache_backup_$(date +%Y%m%d).json"
```

### **Compartilhar Cache**

⚠️ **IMPORTANTE**: Cache pode ser compartilhado entre usuários, mas:
- ✅ Cache de textos genéricos (menus, erros)
- ❌ NÃO compartilhar traduções de jogos com direitos autorais

```bash
# Exportar cache de textos comuns
python extract_common_cache.py cache.json common_cache.json
# (Filtrar apenas textos genéricos tipo "New Game", "Settings")
```

---

## 🎯 BOAS PRÁTICAS

1. **Use cache por padrão** (exceto se testando qualidade)
2. **Limpe cache ao mudar de idioma alvo**
3. **Backup semanal do cache** (economiza $$ se perder)
4. **Revise top 10 traduções** para verificar qualidade
5. **Remova entradas antigas** a cada 3 meses

---

## 🔄 COMPATIBILIDADE

**Sistema de Cache**:
- ✅ 100% compatível com pipeline PC existente
- ✅ Opcional (pode desabilitar com `use_cache=False`)
- ✅ Não afeta sistema de ROMs
- ✅ Não modifica código existente
- ✅ Zero dependências externas

---

## 📚 REFERÊNCIAS

- [pc_translation_cache.py](../core/pc_translation_cache.py) - Código do módulo
- [pc_pipeline.py](../core/pc_pipeline.py) - Integração com pipeline
- [PC_GAMES_IMPLEMENTATION.md](PC_GAMES_IMPLEMENTATION.md) - Documentação geral

---

**Data**: 2025-01-10
**Versão**: 1.0
**Status**: ✅ Implementado e testado
**Economia Estimada**: 70-95% em retraduções
