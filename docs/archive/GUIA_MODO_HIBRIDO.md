# 🤖 Guia do Modo Híbrido - Tradução Inteligente

## ✅ Sistema Implementado com Sucesso!

Você agora tem um sistema **inteligente** que:
- ✅ Usa Gemini (rápido) quando quota disponível
- ✅ **Automaticamente muda** para Ollama quando quota esgotar
- ✅ Continua traduzindo **sem parar**
- ✅ Salva estatísticas de uso

---

## 🎯 Como Usar na Interface

### Passo 1: Abra a Interface

```bash
python rom-translation-framework/interface/interface_tradutor_final.py
```

### Passo 2: Configure o Modo

Na aba **"2. Tradução"**, você verá:

```
┌─────────────────────────────────────────┐
│ Modo de Tradução                        │
├─────────────────────────────────────────┤
│ 🤖 Auto (Gemini → Ollama)               │ ← RECOMENDADO!
│ ⚡ Online Gemini (Google API)            │
│ 🐌 Offline Ollama (Llama 3.2)           │
│ 🌐 Online DeepL (API)                   │
└─────────────────────────────────────────┘
```

**Escolha: 🤖 Auto (Gemini → Ollama)**

### Passo 3: Configure API Key

- Cole sua API Key do Gemini
- Defina Workers: **3**
- Timeout: **120s**

### Passo 4: Traduza!

Clique em **"TRADUZIR COM IA"**

---

## 🚀 O Que Acontece (Modo Auto)

### Início (Com Quota Disponível)

```
[13:00:00] 🤖 AUTO Mode: 500 linhas (Gemini primeiro, Ollama se quota esgotar)
[13:00:01] ✅ Gemini: Disponível
[13:00:01] ✅ Ollama: Disponível
[13:00:02] ⚡ Traduzindo com Gemini...
[13:00:03] ✅ Batch 1/33 completo (15 textos)
[13:00:05] ✅ Batch 2/33 completo (15 textos)
...
```

**Velocidade:** ~1-2 segundos por batch (15 textos)

### Meio (Quota Esgotando)

```
[13:01:30] ✅ Batch 15/33 completo
[13:01:32] ⚠️ Erro: 429 Quota exceeded
[13:01:32] 🔄 Mudou para Ollama (quota Gemini esgotada)
[13:01:35] 🐌 Traduzindo com Ollama...
[13:02:05] ✅ Batch 16/33 completo (15 textos)
...
```

**Velocidade:** ~30 segundos por batch (mas continua!)

### Fim (Estatísticas)

```
[13:15:00] ✅ Tradução completa!

==================================================
📊 ESTATÍSTICAS FINAIS:
   Gemini: 15 requisições (225 textos)
   Ollama: 18 requisições (275 textos)
   Fallbacks: 1
   Total traduzido: 500 textos
==================================================
```

---

## 📊 Comparação dos Modos

| Modo | Velocidade | Quota | Uso GPU | Quando Usar |
|------|------------|-------|---------|-------------|
| **🤖 Auto** | Rápido→Lento | 20→∞ | 0%→60% | **Sempre (padrão)** |
| ⚡ Gemini | Muito rápido | 20/dia | 0% | Tem quota disponível |
| 🐌 Ollama | Lento | ∞ | 60% | Quota esgotada ou offline |
| 🌐 DeepL | Rápido | Pago | 0% | Tem conta DeepL |

---

## 💡 Cenários de Uso

### Cenário 1: Traduzir Jogo Pequeno (< 200 textos)

**Modo:** 🤖 Auto ou ⚡ Gemini

**Resultado:**
- ✅ Usa apenas Gemini (rápido)
- ⏱️ Tempo: 1-2 minutos
- 📊 Quota usada: 1-2 requisições
- 🎯 Restam ~18 requisições no dia

### Cenário 2: Traduzir Jogo Médio (500-1000 textos)

**Modo:** 🤖 Auto (RECOMENDADO)

**O que acontece:**
1. Primeiros 300 textos → Gemini (rápido)
2. Quota esgota → Muda para Ollama automaticamente
3. Restantes 200-700 textos → Ollama (lento mas completa)

**Resultado:**
- ✅ Tradução completa (não para!)
- ⏱️ Tempo: 5-20 minutos
- 📊 Gemini: 20 requisições, Ollama: resto
- 🎯 Melhor dos 2 mundos

### Cenário 3: Traduzir Jogo Grande (10.000+ textos)

**Modo:** 🤖 Auto

**O que acontece:**
1. Dia 1: Usa 20 requisições Gemini (4.000 textos)
2. Muda para Ollama (restantes 6.000 textos)
3. Continua até completar

**Resultado:**
- ✅ Tradução 100% completa
- ⏱️ Tempo: ~2-3 horas (depende da GPU)
- 📊 4.000 textos rápidos + 6.000 lentos
- 🎯 Sem custo, sem parar

### Cenário 4: Quota Gemini Já Esgotada

**Modo:** 🤖 Auto detecta e usa Ollama direto

**Resultado:**
- ✅ Continua funcionando (100% Ollama)
- ⏱️ Mais lento mas completa tudo
- 📊 0 Gemini, 100% Ollama
- 🎯 Sem erro, sem parar

---

## 🔧 Configurações Avançadas

### Ajustar Preferência

Edite [core/hybrid_translator.py](rom-translation-framework/core/hybrid_translator.py:18):

```python
# Prefere Gemini (rápido primeiro)
translator = HybridTranslator(api_key, prefer_gemini=True)

# Prefere Ollama (sempre lento mas nunca paga)
translator = HybridTranslator(api_key, prefer_gemini=False)
```

### Forçar um Modo Específico

```python
from core.hybrid_translator import TranslationMode

# Força apenas Gemini (erro se quota esgotar)
translator.translate_batch(texts, mode=TranslationMode.GEMINI)

# Força apenas Ollama (sempre lento)
translator.translate_batch(texts, mode=TranslationMode.OLLAMA)

# Auto (recomendado)
translator.translate_batch(texts, mode=TranslationMode.AUTO)
```

---

## 📈 Uso da GPU em Diferentes Modos

### Modo Auto (🤖)

```
GPU Usage Timeline:

Gemini Phase (primeiros 15 minutos):
GPU: 0-5% (não usa GPU, API remota)
───────────────────────

Quota esgota → Switch automático

Ollama Phase (resto):
GPU: 30-94% (usa GPU local)
████████████░░░░░░░░░
```

### Modo Gemini Puro (⚡)

```
GPU: 0-5% durante toda tradução
(API remota, não usa sua GPU)
```

### Modo Ollama Puro (🐌)

```
GPU: 30-94% durante toda tradução
████████████████████████████████
(Usa sua GTX 1060 ao máximo)
```

---

## 🎓 Dicas e Truques

### 1. Maximize Eficiência

```
✅ Use modo Auto (padrão)
✅ Configure Workers: 3
✅ Ative cache de traduções
✅ Traduza em horários de baixo uso da GPU
```

### 2. Economize Quota Gemini

```
✅ Use Ollama para testes (modo manual)
✅ Reserve Gemini para tradução final
✅ Ative cache para não re-traduzir
```

### 3. Aproveite Ollama ao Máximo

```
✅ Rode traduções longas à noite (Ollama não tem limite)
✅ Use enquanto GPU está ociosa
✅ Combine com outros workers para paralelizar
```

---

## ⚠️ Solução de Problemas

### Problema: "QuotaManager não disponível"

**Causa:** Arquivos de quota não carregaram

**Solução:**
```bash
# Verifique se arquivos existem
ls rom-translation-framework/core/quota_manager.py
ls rom-translation-framework/core/batch_queue_manager.py
ls rom-translation-framework/core/hybrid_translator.py
```

### Problema: "Ollama não está rodando"

**Causa:** Serviço Ollama não iniciado

**Solução:**
```bash
# Windows
start ollama serve

# Verificar se iniciou
curl http://localhost:11434/api/tags
```

### Problema: Modo Auto não muda para Ollama

**Causa:** Ollama não detectado como disponível

**Solução:**
1. Verifique se Ollama está rodando: `ollama list`
2. Teste manualmente: `ollama run llama3.2:3b "test"`
3. Reinicie a interface

### Problema: Tradução muito lenta

**Causa:** Rodando 100% no Ollama

**Verifique:**
- Quota Gemini está esgotada? (espere reset 00:00)
- GPU está sendo usada? (nvidia-smi)
- Modelo Llama está carregado? (pode demorar 1ª vez)

---

## 📊 Logs e Monitoramento

### Ver Logs em Tempo Real

A interface mostra logs automáticos:

```
[13:00:00] 🤖 AUTO Mode: 500 linhas
[13:00:01] ✅ Gemini: Disponível
[13:00:01] ✅ Ollama: Disponível
[13:00:05] ⚡ Modo: Gemini (Rápido) | Textos: 15
[13:01:32] 🔄 Mudou para Ollama (quota esgotada)
[13:02:00] 🐌 Modo: Ollama (Lento) | Textos: 30
```

### Monitorar GPU (Terminal Separado)

```bash
# Atualiza a cada 1 segundo
watch -n 1 nvidia-smi

# Ou com gráfico
nvidia-smi dmon -s um
```

---

## 🎉 Resumo Final

**Você implementou com sucesso:**

✅ Sistema de gerenciamento de quota Gemini
✅ Fallback automático para Ollama
✅ 3 modos de tradução (Auto, Gemini, Ollama)
✅ Monitoramento de GPU em tempo real
✅ Estatísticas detalhadas de uso
✅ Interface gráfica completa

**Resultado:**
- 🚀 Nunca mais vai parar tradução por quota esgotada
- 💰 Economiza usando Gemini quando possível
- ∞ Ilimitado com Ollama quando necessário
- 📊 Transparente e monitorável

**Agora você pode traduzir jogos completos sem se preocupar!** 🎮✨

---

## 📚 Documentação Relacionada

- [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md) - Sistema de quota
- [INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md) - Tutorial rápido
- [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md) - Análise de GPU
- [exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py) - Exemplos de código

---

**Data:** 2025-12-19
**Versão:** ROM Translation Framework v5.3
**Status:** ✅ COMPLETO E FUNCIONAL
