# 📁 Estrutura do Projeto - ROM Translation Framework v5.3

## 🎯 Visão Geral

```
PROJETO_V5_OFICIAL/
│
├─ 📘 README.md                          ← Comece aqui!
├─ 📘 LEIA_PRIMEIRO.md                   ← Guia principal completo
├─ 📘 INDICE_COMPLETO.md                 ← Índice de tudo
├─ 📘 DIAGRAMA_FLUXO.md                  ← Fluxogramas visuais
│
├─ 🚀 INICIAR_AQUI.bat                   ← Launcher Windows (duplo clique!)
├─ 🔍 verificar_sistema.py               ← Verificar instalação
│
├─ 🛠️ otimizar_arquivo_traducao.py       ← Remove duplicatas (IMPORTANTE!)
├─ 📝 exemplo_traducao_com_quota.py      ← Exemplos de código
│
├─ 📚 Documentação/
│   ├─ GUIA_OTIMIZACAO_RAPIDA.md        ← Arquivos grandes (755k linhas)
│   ├─ GUIA_MODO_HIBRIDO.md             ← Modo Auto explicado
│   ├─ INICIO_RAPIDO_QUOTA.md           ← Sistema de quota (5min)
│   ├─ RELATORIO_OLLAMA_GPU.md          ← Temperatura e GPU
│   └─ GERENCIAMENTO_QUOTA_README.md    ← Detalhes técnicos
│
└─ rom-translation-framework/            ← Framework principal
    ├─ core/                             ← Componentes principais
    ├─ interface/                        ← Interface gráfica
    ├─ docs/                             ← Documentação adicional
    └─ examples/                         ← Exemplos de uso
```

---

## 📂 Arquivos na Raiz (Onde Você Está)

### 🌟 COMECE POR AQUI

| Arquivo | Tipo | Descrição | Quando Abrir |
|---------|------|-----------|--------------|
| **[README.md](README.md)** | 📘 Documentação | Visão geral do projeto | Primeira vez |
| **[LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)** | 📘 Documentação | **Guia completo de uso** | **Sempre primeiro!** |
| **[INDICE_COMPLETO.md](INDICE_COMPLETO.md)** | 📘 Documentação | Índice de todos os arquivos | Procurando algo específico |
| **[DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md)** | 📘 Documentação | Fluxogramas e diagramas visuais | Prefere imagens a texto |

### 🚀 FERRAMENTAS DE INICIALIZAÇÃO

| Arquivo | Tipo | Descrição | Como Usar |
|---------|------|-----------|-----------|
| **[INICIAR_AQUI.bat](INICIAR_AQUI.bat)** | ⚙️ Launcher | Menu interativo (Windows) | Duplo clique! |
| **[verificar_sistema.py](verificar_sistema.py)** | 🔍 Script | Verifica se tudo está OK | `python verificar_sistema.py` |

### 🛠️ SCRIPTS UTILITÁRIOS

| Arquivo | Tipo | Descrição | Como Usar |
|---------|------|-----------|-----------|
| **[otimizar_arquivo_traducao.py](otimizar_arquivo_traducao.py)** | 🚀 Script | **Remove duplicatas** (80% redução!) | `python otimizar_arquivo_traducao.py arquivo.txt` |
| **[exemplo_traducao_com_quota.py](exemplo_traducao_com_quota.py)** | 📝 Exemplo | Exemplos de uso do sistema | `python exemplo_traducao_com_quota.py` |

### 📚 GUIAS TEMÁTICOS

| Arquivo | Tema | Para Quem? |
|---------|------|------------|
| **[GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)** | Acelerar arquivos grandes | Arquivos com > 100k linhas |
| **[GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md)** | Modo Auto (Gemini→Ollama) | Quer melhor dos 2 mundos |
| **[INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md)** | Sistema de quota | Usar Gemini API |
| **[RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md)** | Temperatura e GPU | Preocupado com hardware |
| **[GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md)** | Detalhes técnicos quota | Desenvolvedores/curiosos |

---

## 📦 Framework (Subpasta)

### 📁 `rom-translation-framework/core/` - NÚCLEO DO SISTEMA

**Componentes Essenciais (v5.3):**

| Arquivo | Função | Importância |
|---------|--------|-------------|
| **[quota_manager.py](rom-translation-framework/core/quota_manager.py)** | Gerencia 20 req/dia do Gemini | ⭐⭐⭐ Essencial |
| **[batch_queue_manager.py](rom-translation-framework/core/batch_queue_manager.py)** | Fila com prioridades | ⭐⭐⭐ Essencial |
| **[hybrid_translator.py](rom-translation-framework/core/hybrid_translator.py)** | Fallback Gemini↔Ollama | ⭐⭐⭐ Essencial |
| [pc_pipeline.py](rom-translation-framework/core/pc_pipeline.py) | Pipeline para jogos PC | ⭐⭐ Importante |
| [translation_engine.py](rom-translation-framework/core/translation_engine.py) | Motor de tradução base | ⭐⭐ Importante |
| [pc_text_extractor.py](rom-translation-framework/core/pc_text_extractor.py) | Extrai textos de jogos PC | ⭐ Útil |
| [pc_safe_reinserter.py](rom-translation-framework/core/pc_safe_reinserter.py) | Reinsere traduções | ⭐ Útil |

**Outros Módulos (ROMs clássicas):**
- `rom_analyzer.py` - Analisa ROMs de SNES/NES
- `text_scanner.py` - Escaneia textos em ROMs
- `pointer_scanner.py` - Detecta ponteiros
- `charset_inference.py` - Detecta tabela de caracteres
- `compression_detector.py` - Detecta compressão

### 📁 `rom-translation-framework/interface/` - INTERFACE GRÁFICA

| Arquivo | Função | Importância |
|---------|--------|-------------|
| **[interface_tradutor_final.py](rom-translation-framework/interface/interface_tradutor_final.py)** | **Interface principal (PyQt6)** | ⭐⭐⭐ Essencial |
| **[gemini_api.py](rom-translation-framework/interface/gemini_api.py)** | API do Google Gemini | ⭐⭐⭐ Essencial |
| **[quota_monitor_widget.py](rom-translation-framework/interface/quota_monitor_widget.py)** | Widget de monitoramento | ⭐ Útil |

**Como usar:**
```bash
python rom-translation-framework/interface/interface_tradutor_final.py
```

### 📁 `rom-translation-framework/docs/` - DOCUMENTAÇÃO ADICIONAL

| Arquivo | Conteúdo |
|---------|----------|
| [00_START_HERE.md](rom-translation-framework/docs/00_START_HERE.md) | Guia de início (versão antiga) |
| [QUICK_START_ADVANCED.md](rom-translation-framework/docs/QUICK_START_ADVANCED.md) | Módulos avançados |
| [PC_GAMES_IMPLEMENTATION.md](rom-translation-framework/docs/PC_GAMES_IMPLEMENTATION.md) | Implementação jogos PC |
| [TRANSLATION_CACHE.md](rom-translation-framework/docs/TRANSLATION_CACHE.md) | Sistema de cache |

### 📁 `rom-translation-framework/examples/` - EXEMPLOS DE CÓDIGO

| Arquivo | Exemplo |
|---------|---------|
| [translate_single_file.py](rom-translation-framework/examples/translate_single_file.py) | Traduzir arquivo único |
| [analyze_pc_game.py](rom-translation-framework/examples/analyze_pc_game.py) | Analisar jogo de PC |
| [pipeline_integration_example.py](rom-translation-framework/examples/pipeline_integration_example.py) | Integração completa |

---

## 🎯 Navegação Rápida por Tarefa

### "Quero traduzir AGORA!"

```
1. Leia: README.md (2 min)
2. Execute: verificar_sistema.py
3. Se OK: INICIAR_AQUI.bat (Windows) ou
          python rom-translation-framework/interface/interface_tradutor_final.py
4. Configure modo: 🤖 Auto
5. Traduza!
```

### "Tenho arquivo MUITO GRANDE (> 100k linhas)"

```
1. Leia: GUIA_OTIMIZACAO_RAPIDA.md
2. Execute: python otimizar_arquivo_traducao.py arquivo.txt
3. Use arquivo _unique.txt gerado
4. Abra: interface_tradutor_final.py
5. Traduza! (80% mais rápido)
```

### "Quero entender como funciona"

```
1. Leia: LEIA_PRIMEIRO.md (completo)
2. Leia: DIAGRAMA_FLUXO.md (visual)
3. Leia: GERENCIAMENTO_QUOTA_README.md (técnico)
4. Explore: rom-translation-framework/core/ (código)
```

### "Minha GPU vai esquentar?"

```
1. Leia: RELATORIO_OLLAMA_GPU.md
2. Resposta curta: 60-70°C (seguro até 80°C)
3. Use otimizador para reduzir tempo
4. Use botão PARAR para pausas
```

### "Quota Gemini esgotou, e agora?"

```
1. Leia: GUIA_MODO_HIBRIDO.md
2. Use modo: 🤖 Auto (Gemini → Ollama)
3. Sistema muda automaticamente para Ollama
4. NUNCA para por falta de quota!
```

---

## 📊 Fluxo de Arquivos Durante Tradução

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO DE TRADUÇÃO                            │
└─────────────────────────────────────────────────────────────────┘

1. ENTRADA
   └─ seu_arquivo.txt (755.306 linhas)

2. OTIMIZAÇÃO (OPCIONAL MAS RECOMENDADO)
   └─ otimizar_arquivo_traducao.py
       └─ seu_arquivo_unique.txt (150.000 linhas - 80% redução!)

3. INTERFACE GRÁFICA
   └─ interface_tradutor_final.py
       │
       ├─ Carrega: seu_arquivo_unique.txt
       ├─ Modo: 🤖 Auto (Gemini → Ollama)
       └─ Workers: 3

4. TRADUÇÃO (CORE)
   │
   ├─ batch_queue_manager.py
   │   └─ Divide em batches de 200 textos
   │
   ├─ hybrid_translator.py
   │   │
   │   ├─ FASE 1: Gemini (rápido)
   │   │   └─ gemini_api.py
   │   │       └─ quota_manager.py (controla 20/dia)
   │   │
   │   └─ FASE 2: Ollama (lento mas ilimitado)
   │       └─ Requisições HTTP para localhost:11434
   │
   └─ Progresso salvo em: progresso_traducao.json

5. SAÍDA
   └─ seu_arquivo_unique_traduzido.txt (150.000 linhas em português!)

6. ESTATÍSTICAS
   └─ Gemini: 4.000 textos (10 min)
   └─ Ollama: 146.000 textos (1h 20min)
   └─ TOTAL: 150.000 textos (1h 30min)
```

---

## 🔑 Arquivos de Configuração

Durante o uso, o sistema cria automaticamente:

| Arquivo | Função | Localização |
|---------|--------|-------------|
| `.quota_state.json` | Estado da quota Gemini | Raiz do projeto |
| `progresso_traducao.json` | Progresso da tradução | Raiz do projeto |
| `cache_traducoes.db` | Cache de traduções | `rom-translation-framework/` |

**⚠️ NÃO DELETE ESSES ARQUIVOS!** Eles guardam seu progresso.

---

## 📈 Arquivos Gerados Automaticamente

Quando você usa o otimizador ou tradutor, são criados:

### Pelo Otimizador

```
Entrada:  meu_jogo.txt
Saída:    meu_jogo_unique.txt           (arquivo otimizado)
          meu_jogo_optimization_report.txt  (relatório)
```

### Pelo Tradutor

```
Entrada:  meu_jogo_unique.txt
Saída:    meu_jogo_unique_traduzido.txt  (tradução final)
          progresso_traducao.json         (checkpoint)
```

---

## 🎓 Níveis de Documentação

### 🟢 INICIANTE (Leia PRIMEIRO)

1. [README.md](README.md) - Visão geral (5 min)
2. [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) - Guia completo (15 min)
3. [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md) - Visual (10 min)

**Total:** 30 minutos → Pronto para traduzir!

### 🟡 INTERMEDIÁRIO (Se quiser saber mais)

4. [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)
5. [GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md)
6. [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md)

**Total:** +45 minutos → Domina o sistema!

### 🔴 AVANÇADO (Para desenvolvedores)

7. [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md)
8. [rom-translation-framework/core/](rom-translation-framework/core/) (código-fonte)
9. [rom-translation-framework/docs/](rom-translation-framework/docs/) (docs técnicas)

**Total:** +2 horas → Pode customizar tudo!

---

## 🗺️ Mapa Mental do Projeto

```
ROM Translation Framework v5.3
│
├─ 🎯 OBJETIVO
│   └─ Traduzir jogos (ROMs e PC) usando IA
│
├─ 🧠 INTELIGÊNCIAS ARTIFICIAIS
│   ├─ Google Gemini (rápido, free tier 20/dia)
│   └─ Ollama/Llama (lento, ilimitado, offline)
│
├─ 🔧 FERRAMENTAS
│   ├─ Interface gráfica (PyQt6)
│   ├─ Otimizador (remove duplicatas)
│   └─ Sistema de quota (gerencia limites)
│
├─ 📊 RECURSOS
│   ├─ Modo Auto (fallback automático)
│   ├─ Botão PARAR (salva progresso)
│   ├─ Workers paralelos (3-10)
│   └─ Monitoramento GPU (temperatura)
│
└─ 📚 DOCUMENTAÇÃO
    ├─ Guias de início rápido
    ├─ Guias temáticos
    ├─ Relatórios técnicos
    └─ Exemplos de código
```

---

## 🎯 Checklist de Arquivos Essenciais

Antes de começar a traduzir, confirme que tem:

### ✅ Documentação

- [ ] README.md
- [ ] LEIA_PRIMEIRO.md
- [ ] INDICE_COMPLETO.md

### ✅ Ferramentas

- [ ] INICIAR_AQUI.bat (Windows)
- [ ] verificar_sistema.py
- [ ] otimizar_arquivo_traducao.py

### ✅ Framework Core

- [ ] rom-translation-framework/core/quota_manager.py
- [ ] rom-translation-framework/core/batch_queue_manager.py
- [ ] rom-translation-framework/core/hybrid_translator.py

### ✅ Interface

- [ ] rom-translation-framework/interface/interface_tradutor_final.py
- [ ] rom-translation-framework/interface/gemini_api.py

Se todos estiverem marcados → ✅ **Sistema completo!**

Para verificar automaticamente:
```bash
python verificar_sistema.py
```

---

## 🎉 Resumo

**Tudo que você precisa está aqui!**

```
📘 Documentação completa ✅
🚀 Ferramentas prontas ✅
🔧 Sistema funcional ✅
📊 Exemplos de uso ✅
🎓 Tutoriais passo a passo ✅
```

**Comece agora:** [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)

---

**Versão:** ROM Translation Framework v5.3
**Data:** 2025-12-19
**Status:** ✅ COMPLETO E ORGANIZADO
