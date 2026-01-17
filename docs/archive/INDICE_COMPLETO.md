# 📚 Índice Completo - ROM Translation Framework v5.3

## 🚀 COMECE AQUI

| Arquivo | Descrição | Quando Usar |
|---------|-----------|-------------|
| **[LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)** | **⭐ GUIA PRINCIPAL** - Leia isso primeiro! | Sempre, antes de qualquer coisa |
| **[INICIAR_AQUI.bat](INICIAR_AQUI.bat)** | Launcher automático (Windows) | Atalho rápido para abrir tudo |
| **[DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md)** | Fluxograma visual de como usar | Se preferir diagramas visuais |

---

## 📖 DOCUMENTAÇÃO POR CATEGORIA

### 🎯 Guias Rápidos (5-10 minutos de leitura)

| Arquivo | Conteúdo | Para Quem? |
|---------|----------|------------|
| [INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md) | Como usar sistema de quota em 5 minutos | Iniciantes com Gemini API |
| [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md) | Como acelerar tradução de arquivos grandes | Arquivos com > 100k linhas |
| [GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md) | Modo Auto (Gemini → Ollama) explicado | Quem quer o melhor dos 2 mundos |

### 📊 Relatórios Técnicos

| Arquivo | Conteúdo | Para Quem? |
|---------|----------|------------|
| [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md) | Análise de uso de GPU/temperatura | Preocupados com hardware |
| [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md) | Detalhes do sistema de quota | Desenvolvedores/curiosos |

---

## 🛠️ FERRAMENTAS E SCRIPTS

### Scripts Python

| Arquivo | Função | Comando |
|---------|--------|---------|
| [otimizar_arquivo_traducao.py](otimizar_arquivo_traducao.py) | Remove duplicatas de arquivos | `python otimizar_arquivo_traducao.py arquivo.txt` |
| [exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py) | Exemplos de uso do sistema | `python exemplo_traducao_com_quota.py` |

### Interface Gráfica

| Arquivo | Função | Comando |
|---------|--------|---------|
| [rom-translation-framework/interface/interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py) | **Interface principal** | `python rom-translation-framework/interface/interface_tradutor_final.py` |

---

## ⚙️ COMPONENTES PRINCIPAIS DO SISTEMA

### Core (Núcleo)

| Módulo | Função | Importância |
|--------|--------|-------------|
| [quota_manager.py](rom-translation-framework/core/quota_manager.py) | Gerencia limite de 20 req/dia Gemini | ⭐⭐⭐ Essencial |
| [batch_queue_manager.py](rom-translation-framework/core/batch_queue_manager.py) | Fila de batches com prioridades | ⭐⭐⭐ Essencial |
| [hybrid_translator.py](rom-translation-framework/core/hybrid_translator.py) | Fallback automático Gemini↔Ollama | ⭐⭐⭐ Essencial |
| [pc_pipeline.py](rom-translation-framework/core/pc_pipeline.py) | Pipeline para jogos de PC | ⭐⭐ Importante |
| [translation_engine.py](rom-translation-framework/core/translation_engine.py) | Motor de tradução base | ⭐⭐ Importante |

### Interface

| Módulo | Função | Importância |
|--------|--------|-------------|
| [gemini_api.py](rom-translation-framework/interface/gemini_api.py) | API do Google Gemini | ⭐⭐⭐ Essencial |
| [quota_monitor_widget.py](rom-translation-framework/interface/quota_monitor_widget.py) | Widget de monitoramento visual | ⭐ Útil |

---

## 📊 RECURSOS IMPLEMENTADOS

### ✅ Sistema de Quota Gemini

**Arquivos relacionados:**
- [quota_manager.py](rom-translation-framework/core/quota_manager.py)
- [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md)
- [INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md)

**O que faz:**
- Controla limite de 20 requisições/dia (free tier)
- Salva estado em JSON persistente
- Rate limiting automático (4s entre requests)
- Estimativas de tempo e quota

**Como usar:**
```python
from rom-translation-framework.core.quota_manager import get_quota_manager

quota = get_quota_manager()
status = quota.get_quota_status()
print(f"Restam {status['daily_remaining']} requisições")
```

---

### ✅ Sistema de Fila com Prioridades

**Arquivos relacionados:**
- [batch_queue_manager.py](rom-translation-framework/core/batch_queue_manager.py)

**O que faz:**
- 4 níveis de prioridade (CRITICAL, HIGH, NORMAL, LOW)
- Processamento em background (threads)
- Auto-save a cada 10 batches
- Retoma de onde parou

**Como usar:**
```python
from rom-translation-framework.core.batch_queue_manager import BatchQueueManager, Priority

queue = BatchQueueManager(progress_file="jogo.json")
queue.add_batch(texts_importantes, Priority.HIGH)
queue.start_processing(minha_funcao_traducao, quota_manager)
```

---

### ✅ Modo Híbrido (Auto)

**Arquivos relacionados:**
- [hybrid_translator.py](rom-translation-framework/core/hybrid_translator.py)
- [GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md)

**O que faz:**
- Usa Gemini primeiro (rápido, 1-2s)
- Detecta quota esgotada (erro 429)
- Muda automaticamente para Ollama (lento mas ilimitado)
- Estatísticas detalhadas de uso

**Como usar:**
```python
from rom-translation-framework.core.hybrid_translator import HybridTranslator, TranslationMode

translator = HybridTranslator(api_key="sua_key", prefer_gemini=True)
translations, success, error = translator.translate_batch(
    texts,
    target_language="Portuguese (Brazil)",
    mode=TranslationMode.AUTO  # Automático!
)

print(translator.get_status_message())
# ⚡ Modo: Gemini (Rápido) | Textos: 150 | Gemini: 10 | Ollama: 0
```

---

### ✅ Otimizador de Arquivos

**Arquivos relacionados:**
- [otimizar_arquivo_traducao.py](otimizar_arquivo_traducao.py)
- [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)

**O que faz:**
- Remove linhas duplicadas
- Mantém ordem original
- Redução típica: 50-80%
- Economia de tempo: 5-6 horas (para 755k linhas)

**Como usar:**
```bash
python otimizar_arquivo_traducao.py meu_arquivo.txt

# Gera: meu_arquivo_unique.txt
```

**Resultado esperado:**
```
📊 RESULTADO:
   Linhas originais: 755.306
   Linhas únicas: 150.000
   Redução: 80.1%

   Tempo antes: ~7 horas
   Tempo depois: ~1.4 horas
   Economia: 5.6 horas!
```

---

### ✅ Interface Gráfica com Botão PARAR

**Arquivos relacionados:**
- [interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py)

**Recursos:**
- 3 modos de tradução: Auto, Gemini, Ollama
- Botão PARAR vermelho (50px altura)
- Workers paralelos (1-10 threads)
- Salvamento automático de progresso
- Logs em tempo real

**Modos disponíveis:**
```
🤖 Auto (Gemini → Ollama)    ← RECOMENDADO
⚡ Online Gemini (Google API)
🐌 Offline Ollama (Llama 3.2)
🌐 Online DeepL (API)
```

---

## 🎮 CASOS DE USO

### 1️⃣ Traduzir Jogo de PC (755k+ linhas)

**Arquivos necessários:**
- Interface: [interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py)
- Otimizador: [otimizar_arquivo_traducao.py](otimizar_arquivo_traducao.py)

**Passos:**
1. Otimize arquivo primeiro: `python otimizar_arquivo_traducao.py arquivo.txt`
2. Abra interface: `python rom-translation-framework/interface/interface_tradutor_final.py`
3. Configure modo: `🤖 Auto (Gemini → Ollama)`
4. Carregue arquivo otimizado (_unique.txt)
5. Clique "TRADUZIR COM IA"

**Tempo estimado:** 1-2 horas (com otimização)

**Leia:** [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)

---

### 2️⃣ Traduzir ROM de SNES (< 5k linhas)

**Arquivos necessários:**
- Interface: [interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py)

**Passos:**
1. Abra interface
2. Configure modo: `⚡ Online Gemini` (rápido!)
3. Carregue arquivo
4. Clique "TRADUZIR COM IA"

**Tempo estimado:** 5-30 minutos

**Leia:** [INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md)

---

### 3️⃣ Tradução Offline (sem internet)

**Arquivos necessários:**
- Interface: [interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py)
- Ollama: deve estar instalado e rodando

**Passos:**
1. Inicie Ollama: `ollama serve` (em outro terminal)
2. Abra interface
3. Configure modo: `🐌 Offline Ollama`
4. Carregue arquivo
5. Clique "TRADUZIR COM IA"

**Tempo estimado:** Varia (1-10 horas depende do arquivo)

**Leia:** [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md)

---

## 📈 COMPARAÇÃO DE DESEMPENHO

### Tempo de Tradução (755.306 linhas)

| Método | Tempo | Custo | Requisitos |
|--------|-------|-------|------------|
| **Sequencial (1 texto/vez)** | 20 dias | R$ 0 | Ollama |
| **Paralelo (3 workers, batch 10)** | 3-4 horas | R$ 0 | Ollama + GPU |
| **Com otimização (150k linhas)** | 1-2 horas | R$ 0 | Ollama + GPU |
| **Modo Auto (Gemini + Ollama)** | 1-2 horas | R$ 0 | API Key + GPU |
| **Gemini Puro (pago)** | 10-20 min | $$ | API Key paga |

### Uso de GPU (GTX 1060)

| Modo | GPU | VRAM | Temperatura | Internet |
|------|-----|------|-------------|----------|
| **Gemini** | 0-5% | 0 MB | 48-52°C | ✅ Sim |
| **Ollama** | 30-94% | ~2000 MB | 60-70°C | ❌ Não |
| **Auto** | 0%→60% | 0→2000 MB | 50°C→70°C | ✅ Sim |

---

## 🔧 CONFIGURAÇÃO INICIAL

### Requisitos de Sistema

```
Python: 3.8+
GPU: NVIDIA com CUDA (para Ollama)
RAM: 8GB+ recomendado
Disco: 5GB+ livre (para modelos Ollama)
```

### Instalação Rápida

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Instalar Ollama (opcional, para modo offline)
# Windows: https://ollama.ai/download
# Depois: ollama pull llama3.2:3b

# 3. Configurar API Key do Gemini (opcional)
# Cole no campo da interface ou crie variável:
# export GEMINI_API_KEY="sua_key_aqui"
```

### Primeiro Uso

```bash
# Opção 1: Launcher (Windows)
INICIAR_AQUI.bat

# Opção 2: Interface direta
python rom-translation-framework/interface/interface_tradutor_final.py

# Opção 3: Exemplo de código
python exemplo_traducao_com_quota.py
```

---

## ❓ PERGUNTAS FREQUENTES

### "Qual modo devo usar?"

**Resposta rápida:** `🤖 Auto (Gemini → Ollama)`

**Detalhes:**
- < 4.000 textos → Use `⚡ Gemini` (mais rápido)
- > 4.000 textos → Use `🤖 Auto` (melhor dos 2 mundos)
- Sem internet → Use `🐌 Ollama` (offline)

**Leia:** [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md)

---

### "Preciso otimizar meu arquivo?"

**Se tem > 100.000 linhas:** ✅ **SIM, SEMPRE!**
**Se tem < 100.000 linhas:** Opcional, mas recomendado

**Economia típica:**
- Redução: 50-80% das linhas
- Tempo economizado: 5-6 horas
- Uso de GPU: 80% menos

**Leia:** [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)

---

### "Minha GPU vai esquentar muito?"

**Gemini:** ❌ Não usa GPU (API remota) - 48-52°C
**Ollama:** ✅ Usa GPU (local) - 60-70°C (seguro até 80°C)
**Auto:** Começa 50°C, vai até 70°C máximo

**Dicas:**
- Use otimizador para reduzir tempo
- Use botão PARAR para dar pausas
- Ventile bem o PC

**Leia:** [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md)

---

### "Posso parar a tradução e retomar depois?"

✅ **SIM!** O sistema salva progresso automaticamente.

**Como:**
1. Clique no botão `⏹️ PARAR TRADUÇÃO`
2. Confirme a parada
3. Progresso é salvo em arquivo .json
4. Ao abrir de novo, carregue o mesmo arquivo
5. Sistema retoma de onde parou!

---

### "Por que PC game tem 755k linhas vs SNES com 5k?"

**SNES (1990):**
- RAM: 128 KB (limitação extrema)
- Textos comprimidos ao máximo
- Resultado: 500-5.000 linhas

**PC (2020+):**
- RAM: 8-32 GB (sem limites)
- Textos sem compressão
- Muitas duplicatas
- Logs, debug, múltiplos idiomas
- Resultado: 50.000-500.000+ linhas

**Seu caso:** 755.306 linhas = jogo de PC moderno

**Leia:** [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md) (seção comparação)

---

## 🎯 AÇÕES RECOMENDADAS AGORA

### Para Iniciantes

1. ✅ Leia: [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)
2. ✅ Execute: [INICIAR_AQUI.bat](INICIAR_AQUI.bat)
3. ✅ Escolha modo: `🤖 Auto`
4. ✅ Traduza!

### Para Usuários Avançados

1. ✅ Leia: [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md)
2. ✅ Estude: [hybrid_translator.py](rom-translation-framework/core/hybrid_translator.py)
3. ✅ Customize: Crie seus próprios scripts
4. ✅ Contribua: Melhore o código!

### Para Traduzir HOJE

1. ✅ Otimize: `python otimizar_arquivo_traducao.py arquivo.txt`
2. ✅ Abra: Interface gráfica
3. ✅ Configure: Modo Auto, 3 workers
4. ✅ Traduza: Clique e aguarde 1-2 horas!

---

## 📞 SUPORTE E RECURSOS

### Documentação Completa

Todos os arquivos `.md` neste projeto contêm documentação detalhada.

**Principais:**
- [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) - Visão geral
- [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md) - Fluxogramas visuais
- [GUIA_*.md]() - Guias específicos por tópico

### Exemplos de Código

- [exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py)
- [rom-translation-framework/examples/](rom-translation-framework/examples/)

---

## ✨ RESUMO DO QUE VOCÊ TEM

```
✅ Sistema profissional de tradução de jogos
✅ Modo híbrido inteligente (nunca para por quota)
✅ Otimizador de arquivos (remove duplicatas)
✅ Interface gráfica completa (com botão PARAR)
✅ Suporte a ROMs e jogos de PC
✅ Processamento paralelo otimizado (3-4 horas vs 20 dias)
✅ Controle de temperatura e GPU
✅ Documentação completa em português
✅ Exemplos prontos para usar
✅ 100% gratuito e open source
```

**Versão:** ROM Translation Framework v5.3
**Data:** 2025-12-19
**Status:** ✅ PRONTO PARA USO

---

**🎉 Comece agora:** [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)
