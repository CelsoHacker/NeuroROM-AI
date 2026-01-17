# 📊 Sistema Avançado de Gerenciamento de Quota - Google Gemini API

## Visão Geral

Este sistema foi desenvolvido para resolver o problema de **exceder os limites da API Google Gemini Free Tier** durante traduções em massa. Ele gerencia automaticamente a quota de requisições, divide traduções em lotes otimizados e garante que você nunca ultrapasse o limite diário.

### ⚠️ Problema Original

```
[10:31:37] ⚠️ Erro na tradução: 429 You exceeded your current quota
* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
* limit: 20
* model: gemini-2.5-flash
Please retry in 21.47634486s
```

### ✅ Solução Implementada

- **Controle automático de quota** (20 requisições/dia no free tier)
- **Tradução em lotes otimizada** (até 200 textos por requisição)
- **Fila de prioridades** com agendamento inteligente
- **Pausa automática** quando atingir limite
- **Salvamento de progresso** incremental
- **Retomada automática** no dia seguinte

---

## 📦 Componentes do Sistema

### 1. **QuotaManager** ([core/quota_manager.py](rom-translation-framework/core/quota_manager.py))

Gerencia os limites da API Gemini com precisão.

**Recursos:**
- ✅ Contador persistente de requisições diárias
- ✅ Reset automático às 00:00
- ✅ Rate limiting adaptativo (4s entre requisições)
- ✅ Margem de segurança de 20%
- ✅ Estimativa de batches necessários

**Exemplo de uso:**

```python
from core.quota_manager import get_quota_manager

# Obter instância singleton
quota_mgr = get_quota_manager()

# Verificar se pode fazer requisição
can_request, error_msg = quota_mgr.can_make_request()

if can_request:
    # Fazer requisição
    quota_mgr.record_request(success=True)
else:
    print(error_msg)

# Obter estatísticas
stats = quota_mgr.get_stats()
print(f"Uso: {stats['daily_used']}/{stats['daily_limit']}")
```

### 2. **BatchQueueManager** ([core/batch_queue_manager.py](rom-translation-framework/core/batch_queue_manager.py))

Sistema de fila de prioridades para tradução em lotes.

**Recursos:**
- ✅ Fila com 4 níveis de prioridade (CRITICAL, HIGH, NORMAL, LOW)
- ✅ Processamento em background thread-safe
- ✅ Salvamento automático de progresso
- ✅ Pausa/retomada de traduções
- ✅ Retry automático de batches falhados

**Exemplo de uso:**

```python
from core.batch_queue_manager import BatchQueueManager, Priority

# Criar gerenciador
queue = BatchQueueManager(
    progress_file="traducao_progresso.json",
    auto_save_interval=10  # Salva a cada 10 batches
)

# Adicionar batches com prioridades
queue.add_batch(
    texts=["Menu", "Options", "Quit"],
    priority=Priority.CRITICAL,
    metadata={'tipo': 'UI'}
)

queue.add_batch(
    texts=["Quest description..."],
    priority=Priority.NORMAL,
    metadata={'tipo': 'Gameplay'}
)

# Definir função de tradução
def minha_funcao_traducao(textos):
    # Sua lógica de tradução aqui
    traducoes, sucesso, erro = translate_batch(textos, API_KEY)
    return traducoes, sucesso, erro

# Iniciar processamento
queue.start_processing(
    translate_function=minha_funcao_traducao,
    quota_manager=quota_mgr
)

# Pausar se necessário
queue.pause()

# Retomar
queue.resume()

# Parar completamente
queue.stop()
```

### 3. **Gemini API Integrado** ([interface/gemini_api.py](rom-translation-framework/interface/gemini_api.py))

API de tradução com controle de quota integrado.

**Funções principais:**

```python
from interface.gemini_api import (
    translate_batch,
    get_quota_status,
    estimate_translation_quota,
    print_quota_estimate
)

# Traduzir com controle automático de quota
textos = ["Hello", "World"]
traducoes, sucesso, erro = translate_batch(
    textos,
    api_key="SUA_API_KEY",
    target_language="Portuguese (Brazil)"
)

# Verificar status da quota
status = get_quota_status()
print(f"Restam {status['daily_remaining']} requisições hoje")

# Estimar se pode completar tradução
estimativa = estimate_translation_quota(
    total_texts=5000,
    batch_size=200
)

if estimativa['can_complete_today']:
    print("✅ Pode completar hoje!")
else:
    print(f"⚠️ Tradução levará {estimativa['completion_date']}")
```

### 4. **Widget de Monitoramento** ([interface/quota_monitor_widget.py](rom-translation-framework/interface/quota_monitor_widget.py))

Interface gráfica para monitorar quota em tempo real.

**Recursos:**
- 🟢 Indicador visual de uso (verde/amarelo/vermelho)
- 📊 Barra de progresso
- ⏰ Contador de tempo até reset
- 📈 Taxa de sucesso das requisições
- 🔄 Auto-atualização configurável

**Uso standalone:**

```python
from interface.quota_monitor_widget import open_quota_monitor
from core.quota_manager import get_quota_manager

quota_mgr = get_quota_manager()
open_quota_monitor(quota_mgr)
```

**Uso integrado:**

```python
from interface.quota_monitor_widget import QuotaMonitorWidget

# Dentro de sua interface Tkinter/CustomTkinter
monitor = QuotaMonitorWidget(parent_frame, quota_manager=quota_mgr)
monitor.pack(fill="both", expand=True)
```

---

## 🚀 Guia de Uso

### Cenário 1: Tradução Simples

Para traduções pequenas (< 20 batches):

```python
from interface.gemini_api import translate_batch

textos = ["texto1", "texto2", "texto3"]
traducoes, sucesso, erro = translate_batch(
    textos,
    api_key="SUA_API_KEY",
    target_language="Portuguese (Brazil)"
)

if sucesso:
    for orig, trad in zip(textos, traducoes):
        print(f"{orig} → {trad}")
```

### Cenário 2: Tradução Grande (Recomendado)

Para traduções grandes (> 20 batches):

```python
from core.batch_queue_manager import BatchQueueManager, Priority
from core.quota_manager import get_quota_manager
from interface.gemini_api import translate_batch

# 1. Criar gerenciadores
queue = BatchQueueManager(progress_file="meu_projeto.json")
quota = get_quota_manager()

# 2. Adicionar textos à fila (auto-divide em batches)
todos_os_textos = carregar_textos_do_jogo()  # Exemplo: 5000 textos

batch_ids = queue.add_batches_auto(
    all_texts=todos_os_textos,
    batch_size=200,
    detect_priority=True  # Detecta prioridade automaticamente
)

# 3. Definir função de tradução
def traduzir(textos):
    return translate_batch(textos, API_KEY, "Portuguese (Brazil)")

# 4. Configurar callbacks (opcional)
queue.on_batch_complete = lambda b: print(f"✅ Batch {b.batch_id} completo")
queue.on_quota_exceeded = lambda b: print("⛔ Quota esgotada - pausando")

# 5. Iniciar processamento
queue.start_processing(traduzir, quota)

# 6. Aguardar conclusão
while queue.is_running:
    time.sleep(5)
    print(queue.get_status_message())

# 7. Obter todas as traduções
todas_traducoes = queue.get_all_translations()
```

### Cenário 3: Retomar Tradução Interrompida

Se a tradução foi interrompida (quota esgotada ou fechou o programa):

```python
# Cria gerenciador com mesmo arquivo de progresso
queue = BatchQueueManager(progress_file="meu_projeto.json")

# O progresso é carregado automaticamente!
stats = queue.get_stats()
print(f"Progresso anterior: {stats['batches_processed']} batches completos")
print(f"Batches pendentes: {stats['batches_pending']}")

# Retry batches falhados (opcional)
queue.retry_failed()

# Continua de onde parou
queue.start_processing(traduzir, quota)
```

---

## 📈 Limites da API Gemini Free Tier

| Métrica | Valor |
|---------|-------|
| **Requisições por dia** | 20 |
| **Requisições por minuto** | ~15 |
| **Delay mínimo entre requisições** | 4 segundos |
| **Textos por requisição** | 200 (recomendado) |
| **Reset diário** | 00:00 (fuso local) |

### Cálculos Importantes

**Com tradução otimizada:**
- 20 requisições/dia × 200 textos/requisição = **4.000 textos/dia**
- Para 10.000 textos: **3 dias** (com quota free)

**Sem otimização (1 texto por requisição):**
- 20 requisições/dia × 1 texto/requisição = **20 textos/dia**
- Para 10.000 textos: **500 dias!** ❌

**💡 Economia: 25.000% mais eficiente!**

---

## 🛠️ Instalação e Configuração

### 1. Instalar Dependências

```bash
pip install google-generativeai customtkinter
```

### 2. Obter API Key do Google Gemini

1. Acesse: https://ai.google.dev/
2. Faça login com sua conta Google
3. Vá em "Get API Key"
4. Crie uma nova API key
5. Copie a chave

### 3. Configurar no Projeto

```python
# Opção 1: Passar diretamente
API_KEY = "sua_api_key_aqui"

# Opção 2: Variável de ambiente
import os
API_KEY = os.getenv('GEMINI_API_KEY')

# Opção 3: Arquivo de configuração (NUNCA commite no git!)
import json
with open('config.json') as f:
    config = json.load(f)
    API_KEY = config['api_key']
```

### 4. Testar Instalação

```bash
python exemplo_traducao_com_quota.py
```

---

## 📊 Monitoramento e Estatísticas

### Via Código

```python
from interface.gemini_api import get_quota_status

status = get_quota_status()

print(f"Usadas: {status['daily_used']}")
print(f"Restantes: {status['daily_remaining']}")
print(f"Uso: {status['usage_percent']:.0f}%")
print(f"Reset em: {status['hours_until_reset']:.1f}h")
print(f"Taxa de sucesso: {status['success_rate_last_hour']:.0f}%")
```

### Via Interface Gráfica

```python
from interface.quota_monitor_widget import open_quota_monitor
from core.quota_manager import get_quota_manager

open_quota_monitor(get_quota_manager())
```

### Arquivos de Persistência

O sistema cria os seguintes arquivos automaticamente:

```
gemini_quota.json              # Estado da quota (requisições usadas, timestamp)
translation_queue.json         # Progresso da fila (batches, traduções)
translation_cache.json         # Cache de traduções (evita re-traduzir)
```

**⚠️ IMPORTANTE:** Não delete estes arquivos manualmente ou você perderá:
- Contador de requisições do dia
- Progresso de traduções em andamento
- Cache de traduções já feitas

---

## 🔧 Configurações Avançadas

### Ajustar Limites

Edite [core/quota_manager.py](rom-translation-framework/core/quota_manager.py:18-21):

```python
class GeminiQuotaManager:
    # Limites do Free Tier
    FREE_TIER_DAILY_LIMIT = 20          # Requisições/dia
    FREE_TIER_RPM = 15                  # Requisições/minuto
    MIN_DELAY_BETWEEN_REQUESTS = 4.0    # Segundos
    SAFETY_MARGIN = 0.2                 # 20% de margem
```

### Ajustar Tamanho do Batch

Edite [interface/gemini_api.py](rom-translation-framework/interface/gemini_api.py:34):

```python
MAX_BATCH_SIZE = 200  # Até 200 textos por requisição
```

**💡 Recomendação:**
- **Textos curtos** (< 50 chars): 200 textos/batch
- **Textos médios** (50-200 chars): 100 textos/batch
- **Textos longos** (> 200 chars): 50 textos/batch

### Detectar Prioridades Automaticamente

Customize [core/batch_queue_manager.py](rom-translation-framework/core/batch_queue_manager.py:154-174):

```python
def _detect_priority(self, texts: List[str]) -> Priority:
    text_combined = ' '.join(texts).lower()

    # Adicione suas próprias palavras-chave
    if 'seu_criterio' in text_combined:
        return Priority.CRITICAL

    return Priority.NORMAL
```

---

## ⚠️ Tratamento de Erros

### Erro 429: Quota Exceeded

**Causa:** Limite diário atingido

**Solução automática:**
```python
# O sistema detecta automaticamente e:
# 1. Pausa o processamento
# 2. Salva o progresso
# 3. Informa tempo até reset
# 4. Retoma automaticamente no dia seguinte (se em loop)
```

**Solução manual:**
```python
# Aguarde o reset (00:00) e execute novamente
queue = BatchQueueManager(progress_file="meu_projeto.json")
queue.start_processing(traduzir, quota)  # Continua de onde parou
```

### Erro: Rate Limit

**Causa:** Requisições muito rápidas

**Solução automática:**
```python
# O QuotaManager aguarda automaticamente o tempo necessário
# MIN_DELAY_BETWEEN_REQUESTS = 4.0s
```

### Erro: API Key Inválida

**Solução:**
```python
from interface.gemini_api import test_api_key

sucesso, mensagem = test_api_key("sua_api_key")
if not sucesso:
    print(f"Erro: {mensagem}")
```

---

## 📚 Exemplos Práticos

Veja [exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py) para 5 exemplos completos:

1. **Tradução Simples** - Traduzir poucos textos com controle de quota
2. **Estimativa de Quota** - Verificar se pode completar antes de iniciar
3. **Fila de Prioridades** - Sistema completo com salvamento automático
4. **Tradução Massiva** - Simula jogo grande (3.000+ textos)
5. **Monitoramento** - Visualizar quota em tempo real

**Executar:**
```bash
python exemplo_traducao_com_quota.py
```

---

## 🎯 Melhores Práticas

### ✅ DO

- ✅ Use `BatchQueueManager` para traduções > 1000 textos
- ✅ Sempre verifique quota antes de iniciar traduções grandes
- ✅ Salve progresso incrementalmente
- ✅ Use prioridades para textos críticos (UI, erros)
- ✅ Monitore taxa de sucesso
- ✅ Mantenha cache de traduções ativo

### ❌ DON'T

- ❌ Nunca delete arquivos `.json` de progresso manualmente
- ❌ Não ignore mensagens de quota excedida
- ❌ Não traduza texto por texto (use batches!)
- ❌ Não commite API keys no git
- ❌ Não desabilite safety margin (pode causar rate limit)

---

## 🤝 Contribuindo

Melhorias sugeridas:

- [ ] Suporte para múltiplas API keys (rotação)
- [ ] Dashboard web para monitoramento
- [ ] Exportar relatórios de uso em CSV
- [ ] Integração com outros modelos (Claude, GPT)
- [ ] Detecção automática de textos duplicados

---

## 📄 Licença

Este código é parte do **ROM Translation Framework v5.3**

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique este README primeiro
2. Execute [exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py)
3. Confira os logs em tempo real
4. Verifique arquivos de persistência

---

## 🎉 Resumo

Com este sistema você consegue:

- ✅ Traduzir **até 4.000 textos por dia** (vs 20 sem otimização)
- ✅ **Nunca exceder** o limite da API
- ✅ **Retomar** traduções interrompidas automaticamente
- ✅ **Priorizar** textos importantes
- ✅ **Monitorar** uso em tempo real
- ✅ **Economizar** quota com cache inteligente

**Resultado:** Tradução eficiente, confiável e profissional! 🚀
