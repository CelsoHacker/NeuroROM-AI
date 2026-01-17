# 🚀 Início Rápido - Sistema de Quota

## Em 5 Minutos

### 1️⃣ **Verificar Status da Quota**

```python
from interface.gemini_api import get_quota_status, get_quota_stats_message

# Mensagem rápida
print(get_quota_stats_message())
# 🟢 API Gemini: 5/20 requisições (25%) | Reset em 18.5h

# Detalhes completos
status = get_quota_status()
print(f"Restam {status['daily_remaining']} requisições hoje")
```

---

### 2️⃣ **Traduzir Pequena Quantidade (< 1000 textos)**

```python
from interface.gemini_api import translate_batch

textos = ["Hello", "World", "Game Over"]
API_KEY = "sua_api_key_aqui"

traducoes, sucesso, erro = translate_batch(
    textos,
    API_KEY,
    target_language="Portuguese (Brazil)"
)

if sucesso:
    for t in traducoes:
        print(t.strip())
```

**✅ Pronto! O sistema controla a quota automaticamente.**

---

### 3️⃣ **Traduzir Grande Quantidade (> 1000 textos) - RECOMENDADO**

```python
from core.batch_queue_manager import BatchQueueManager, Priority
from core.quota_manager import get_quota_manager
from interface.gemini_api import translate_batch

# Seus textos (exemplo: 5000 textos de um jogo)
todos_textos = carregar_textos()  # Sua função
API_KEY = "sua_api_key"

# Setup
queue = BatchQueueManager(progress_file="meu_jogo.json")
quota = get_quota_manager()

# Adiciona à fila (divide automaticamente em batches)
queue.add_batches_auto(todos_textos, batch_size=200)

# Função de tradução
def traduzir(textos):
    return translate_batch(textos, API_KEY, "Portuguese (Brazil)")

# Processa
queue.start_processing(traduzir, quota)

# Aguarda
import time
while queue.is_running:
    print(queue.get_status_message())
    time.sleep(5)

# Pega traduções
resultado = queue.get_all_translations()
```

**✅ Recursos automáticos:**
- ⏸️ Pausa quando quota esgotar
- 💾 Salva progresso a cada 10 batches
- 🔄 Retoma automaticamente no dia seguinte

---

### 4️⃣ **Estimar Antes de Traduzir**

```python
from interface.gemini_api import print_quota_estimate

total_textos = 5000

# Mostra estimativa visual
print_quota_estimate(total_textos, batch_size=200)
```

**Saída:**
```
============================================================
📊 ESTIMATIVA DE TRADUÇÃO COM GEMINI API
============================================================
Total de textos: 5,000
Batches necessários: 25 (até 200 textos/batch)
Quota disponível hoje: 15 requisições
Tempo estimado: 1.7 minutos
------------------------------------------------------------
⚠️ NÃO PODE COMPLETAR HOJE
   Hoje: 3,000 textos
   Amanhã: 2,000 textos
============================================================
```

---

## 📊 Comandos Úteis

### Ver Status

```python
from interface.gemini_api import get_quota_stats_message
print(get_quota_stats_message())
```

### Retomar Tradução Interrompida

```python
# Usa o mesmo nome de arquivo de antes
queue = BatchQueueManager(progress_file="meu_jogo.json")

# Progresso é carregado automaticamente!
print(f"{queue.batches_processed} batches já completos")

# Continua
queue.start_processing(traduzir, quota)
```

### Monitorar em Tempo Real (GUI)

```python
from interface.quota_monitor_widget import open_quota_monitor
from core.quota_manager import get_quota_manager

open_quota_monitor(get_quota_manager())
```

---

## ⚠️ Erros Comuns

### ❌ Erro: "Quota exceeded"

**Solução:** Sistema pausa automaticamente. Aguarde reset (00:00) ou execute amanhã.

```python
# O progresso foi salvo! Só executar de novo:
queue = BatchQueueManager(progress_file="meu_jogo.json")
queue.start_processing(traduzir, quota)
```

### ❌ Erro: "API Key inválida"

**Solução:** Teste sua key:

```python
from interface.gemini_api import test_api_key

sucesso, msg = test_api_key("sua_key")
print(msg)
```

---

## 💡 Dicas Rápidas

1. **Sempre use batches de 200 textos** (máximo permitido)
2. **Para jogos grandes, use BatchQueueManager** (salvamento automático)
3. **Verifique estimativa antes** de começar traduções longas
4. **Nunca delete arquivos .json** (são seus checkpoints!)
5. **Cache economiza quota** - textos repetidos não são retraduzidos

---

## 📚 Exemplos Prontos

Execute:
```bash
python exemplo_traducao_com_quota.py
```

Escolha:
- **Exemplo 1:** Tradução simples (5 textos)
- **Exemplo 2:** Ver estimativa
- **Exemplo 3:** Fila completa com prioridades ⭐ **RECOMENDADO**
- **Exemplo 5:** Monitorar quota

---

## 🎯 Resumo Visual

```
┌─────────────────────────────────────────────────────────┐
│  QUOTA DIÁRIA: 20 requisições                          │
│  BATCH SIZE: 200 textos/requisição                     │
│  MÁXIMO: 4.000 textos/dia                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Textos > 1000?                                        │
│      ├─ SIM → Use BatchQueueManager ✅                 │
│      └─ NÃO  → Use translate_batch() direto            │
│                                                         │
│  Quota baixa? (< 5 requisições)                        │
│      ├─ SIM → Aguarde reset ou use prioridades        │
│      └─ NÃO  → Pode traduzir normalmente               │
│                                                         │
│  Tradução interrompida?                                │
│      └─ Execute novamente com mesmo progress_file ✅   │
│         (Retoma de onde parou!)                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## ⏱️ Tempos de Tradução

| Textos | Batches | Requisições | Tempo Estimado | Dias |
|--------|---------|-------------|----------------|------|
| 100    | 1       | 1           | 5s             | 1    |
| 1.000  | 5       | 5           | 25s            | 1    |
| 4.000  | 20      | 20          | 1m 40s         | 1    |
| 10.000 | 50      | 50          | 4m 10s         | 3    |
| 50.000 | 250     | 250         | 21m            | 13   |

**💰 Com quota paga:** Mesmos tempos, mas completa em 1 dia!

---

Pronto! Agora você pode traduzir **sem medo de exceder a quota**! 🎉
