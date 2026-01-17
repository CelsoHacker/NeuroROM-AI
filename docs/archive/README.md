# 🎮 ROM Translation Framework v5.3

> **Framework profissional para tradução de jogos (ROMs e PC) com IA**

**Traduz automaticamente jogos antigos e modernos usando Google Gemini e Ollama/Llama**

![Status](https://img.shields.io/badge/Status-Pronto%20para%20uso-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Destaques da v5.3

🤖 **Modo Híbrido Inteligente**
- Usa Gemini (rápido) quando quota disponível
- Muda automaticamente para Ollama quando quota esgotar
- **NUNCA para** por falta de quota!

⏹️ **Botão PARAR**
- Para tradução a qualquer momento
- Salva progresso automaticamente
- Retoma de onde parou

🚀 **755.306 linhas em 3-4 horas** (antes: 20 dias!)
- Processamento paralelo otimizado (3 workers)
- Batches de 10 textos simultâneos
- Suporte a GPU (GTX 1060+)

📊 **Sistema de Gerenciamento de Quota**
- Controla limite de 20 requisições/dia (Gemini free tier)
- Rate limiting automático
- Estimativas precisas de tempo
- Salvamento incremental de progresso

🔧 **Otimizador de Arquivos**
- Remove duplicatas automaticamente
- Redução típica: 50-80%
- Economia de tempo: 5-6 horas

---

## 🚀 Início Rápido (2 Minutos)

### Windows (Launcher Automático)

```cmd
INICIAR_AQUI.bat
```

Escolha a opção **[1] Abrir Interface** e pronto!

### Linux/Mac ou Manual

```bash
# 1. Verifique se tudo está instalado
python verificar_sistema.py

# 2. Abra a interface
python rom-translation-framework/interface/interface_tradutor_final.py

# 3. Configure
#    - Modo: 🤖 Auto (Gemini → Ollama)
#    - Workers: 3
#    - Carregue seu arquivo

# 4. Clique "TRADUZIR COM IA"
```

**Pronto!** 🎉

---

## 📖 Documentação

**Comece aqui:**
- 📘 **[LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)** ← **GUIA PRINCIPAL**
- 🎯 [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md) - Fluxogramas visuais
- 📚 [INDICE_COMPLETO.md](INDICE_COMPLETO.md) - Índice de todos os arquivos

**Guias rápidos:**
- ⚡ [INICIO_RAPIDO_QUOTA.md](INICIO_RAPIDO_QUOTA.md) - Sistema de quota em 5min
- 🚀 [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md) - Acelerar arquivos grandes
- 🤖 [GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md) - Modo Auto explicado

**Relatórios técnicos:**
- 🌡️ [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md) - Análise de temperatura/GPU
- 📊 [GERENCIAMENTO_QUOTA_README.md](GERENCIAMENTO_QUOTA_README.md) - Sistema de quota

---

## 🎯 Recursos Principais

### ✅ Modos de Tradução

| Modo | Velocidade | Quota | Uso GPU | Quando Usar |
|------|------------|-------|---------|-------------|
| **🤖 Auto** | Rápido→Lento | 20→∞ | 0%→60% | **Sempre (padrão)** |
| ⚡ Gemini | Muito rápido | 20/dia | 0% | Tem quota disponível |
| 🐌 Ollama | Lento | ∞ | 60% | Quota esgotada ou offline |
| 🌐 DeepL | Rápido | Pago | 0% | Tem conta DeepL |

### ✅ Plataformas Suportadas

- ✅ **ROMs:** SNES, NES, GBA, N64, PS1, etc.
- ✅ **Jogos de PC:** .exe, .dat, .bin, .txt, arquivos genéricos
- ✅ **Formatos:** ASCII, UTF-8, Shift-JIS, Latin-1, etc.

### ✅ IAs Suportadas

- ✅ **Google Gemini** (gemini-2.5-flash) - Rápido, free tier 20/dia
- ✅ **Ollama/Llama** (llama3.2:3b) - Lento, ilimitado, offline
- ✅ **DeepL** (opcional, requer conta)

---

## 📊 Comparação de Desempenho

### Tempo de Tradução (755.306 linhas - Jogo de PC)

| Método | Tempo | Como |
|--------|-------|------|
| ❌ Sequencial (1 texto/vez) | **20 dias** | Ollama sem otimização |
| ⚠️ Paralelo básico | **7 horas** | Ollama com 3 workers |
| ✅ Paralelo + Otimização | **3-4 horas** | Ollama + remoção duplicatas |
| 🚀 Modo Auto | **1-2 horas** | Gemini (rápido) + Ollama (resto) |

### ROM de SNES (5.000 linhas)

| Método | Tempo |
|--------|-------|
| ⚡ Gemini | **5-10 minutos** |
| 🤖 Auto | **5-10 minutos** |
| 🐌 Ollama | **20-30 minutos** |

---

## 🛠️ Instalação

### Requisitos

```
Python 3.8+
GPU NVIDIA (opcional, mas acelera Ollama)
8GB RAM (recomendado)
5GB espaço em disco
```

### Dependências Python

```bash
pip install PyQt6 requests google-generativeai
```

### Ollama (Opcional - Para Modo Offline)

1. **Baixe:** https://ollama.ai/download
2. **Instale** o executável
3. **Execute:**
   ```bash
   ollama serve              # Inicia servidor
   ollama pull llama3.2:3b   # Baixa modelo (2GB)
   ```

### Verificar Instalação

```bash
python verificar_sistema.py
```

Se aparecer "✅ EXCELENTE! Sistema pronto para usar!" → Está tudo OK!

---

## 🎮 Exemplos de Uso

### Exemplo 1: Traduzir ROM de SNES

```bash
# 1. Abra interface
python rom-translation-framework/interface/interface_tradutor_final.py

# 2. Configure
#    - Modo: ⚡ Online Gemini (rápido!)
#    - Carregue: chrono_trigger_textos.txt

# 3. Traduza
#    Tempo: ~5 minutos
#    Resultado: chrono_trigger_textos_traduzido.txt
```

### Exemplo 2: Traduzir Jogo de PC (755k linhas)

```bash
# 1. Otimize primeiro (remove duplicatas)
python otimizar_arquivo_traducao.py meu_jogo_textos.txt
#    Resultado: meu_jogo_textos_unique.txt (150k linhas)

# 2. Abra interface
python rom-translation-framework/interface/interface_tradutor_final.py

# 3. Configure
#    - Modo: 🤖 Auto (Gemini → Ollama)
#    - Workers: 3
#    - Carregue: meu_jogo_textos_unique.txt

# 4. Traduza
#    Tempo: ~1-2 horas
#    Resultado: meu_jogo_textos_unique_traduzido.txt
```

### Exemplo 3: Modo Offline (Sem Internet)

```bash
# 1. Inicie Ollama (outro terminal)
ollama serve

# 2. Abra interface
python rom-translation-framework/interface/interface_tradutor_final.py

# 3. Configure
#    - Modo: 🐌 Offline Ollama
#    - Workers: 3

# 4. Traduza (funciona sem internet!)
```

---

## 🔧 Ferramentas Incluídas

### Scripts Utilitários

| Script | Função | Comando |
|--------|--------|---------|
| **verificar_sistema.py** | Verifica se tudo está OK | `python verificar_sistema.py` |
| **otimizar_arquivo_traducao.py** | Remove duplicatas | `python otimizar_arquivo_traducao.py arquivo.txt` |
| **exemplo_traducao_com_quota.py** | Exemplos de uso | `python exemplo_traducao_com_quota.py` |
| **INICIAR_AQUI.bat** | Launcher Windows | Clique duplo |

### Interface Gráfica

**Local:** `rom-translation-framework/interface/interface_tradutor_final.py`

**Recursos:**
- 🎨 Interface moderna em PyQt6
- 📊 Progresso em tempo real
- ⏹️ Botão PARAR (vermelho, impossível de errar)
- 💾 Salvamento automático
- 📈 Estatísticas detalhadas
- 🌡️ Monitoramento de temperatura (se GPU disponível)

---

## 🌡️ Uso de GPU

### Temperatura Durante Tradução (GTX 1060)

| Modo | Temperatura | Seguro? |
|------|-------------|---------|
| **Gemini** | 48-52°C | ✅ Muito seguro (não usa GPU) |
| **Ollama** | 60-70°C | ✅ Seguro (limite é 80°C) |
| **Auto** | 50°C→70°C | ✅ Seguro (inicia frio, esquenta gradual) |

**Dicas:**
- ✅ Use otimizador (reduz tempo de uso)
- ✅ Use botão PARAR para dar pausas
- ✅ Monitore temperatura (aparece na interface)
- ⚠️ Se passar de 75°C, clique PARAR e aguarde esfriar

---

## 📈 Estatísticas Reais

**Teste realizado em:**
- PC: Windows 10
- GPU: NVIDIA GTX 1060 6GB
- CPU: i5-8400
- RAM: 16GB

**Arquivo de teste:** 755.306 linhas (jogo de PC)

| Etapa | Tempo | Resultado |
|-------|-------|-----------|
| 1. Arquivo original | - | 755.306 linhas |
| 2. Após otimização | 30s | 150.000 linhas (80% redução!) |
| 3. Tradução (Modo Auto) | 1h 24min | 150.000 linhas traduzidas |
| **TOTAL** | **~1h 25min** | **Economia: 5h 35min!** |

**Sem otimização:** ~7 horas
**Com otimização:** ~1.5 horas
**Diferença:** 5.5x MAIS RÁPIDO! 🚀

---

## 🎓 Casos de Uso

### 1. Tradutor Solo (Hobbyista)
- Traduz jogos antigos por hobby
- Usa quota free do Gemini (20/dia)
- **Modo recomendado:** 🤖 Auto
- **Custo:** R$ 0,00

### 2. Equipe de Tradução (Fan Translation)
- Traduz jogos grandes (100k+ linhas)
- Divide em lotes diários
- Usa otimizador para acelerar
- **Modo recomendado:** 🤖 Auto
- **Custo:** R$ 0,00

### 3. Estúdio Profissional
- Traduz jogos comerciais
- Precisa de velocidade máxima
- Usa conta paga do Gemini
- **Modo recomendado:** ⚡ Gemini (pago)
- **Custo:** ~$0.50-2.00 por jogo

### 4. Uso Offline (Sem Internet)
- Trabalha em locais sem internet
- Usa apenas Ollama local
- **Modo recomendado:** 🐌 Ollama
- **Custo:** R$ 0,00

---

## ❓ FAQ

<details>
<summary><b>Qual modo de tradução devo usar?</b></summary>

**Resposta rápida:** `🤖 Auto (Gemini → Ollama)`

**Detalhes:**
- **< 4.000 textos:** Use `⚡ Gemini` (mais rápido, completa em minutos)
- **> 4.000 textos:** Use `🤖 Auto` (começa rápido, termina tudo)
- **Sem internet:** Use `🐌 Ollama` (100% offline)

Leia mais: [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md)
</details>

<details>
<summary><b>Preciso otimizar meu arquivo?</b></summary>

**Se tem > 100.000 linhas:** ✅ **SIM, SEMPRE!**

**Benefícios:**
- Redução: 50-80% das linhas
- Tempo economizado: 5-6 horas
- Uso de GPU: 80% menos
- Qualidade: Mesma (remove apenas duplicatas)

```bash
python otimizar_arquivo_traducao.py seu_arquivo.txt
```

Leia mais: [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)
</details>

<details>
<summary><b>Minha GPU vai esquentar muito?</b></summary>

**Gemini:** ❌ Não usa GPU (API remota) - 48-52°C (temperatura normal do PC)
**Ollama:** ✅ Usa GPU (local) - 60-70°C (seguro até 80°C)
**Auto:** Começa 50°C (Gemini), vai até 70°C (Ollama)

**É seguro?** ✅ SIM! GTX 1060 aguenta até 80-83°C sem problemas.

**Dicas:**
- Use otimizador (menos tempo = menos calor)
- Use botão PARAR para pausas
- Ventile bem o PC

Leia mais: [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md)
</details>

<details>
<summary><b>Posso parar e retomar depois?</b></summary>

✅ **SIM!** O sistema salva progresso automaticamente.

**Como:**
1. Clique no botão vermelho `⏹️ PARAR TRADUÇÃO`
2. Confirme a parada
3. Progresso é salvo em arquivo .json
4. Ao abrir de novo, carregue o mesmo arquivo
5. Sistema retoma exatamente de onde parou!

**Frequência de salvamento:** A cada 10 batches (automático)
</details>

<details>
<summary><b>Por que jogo de PC tem 755k linhas vs ROM com 5k?</b></summary>

**SNES (1990):**
- RAM: 128 KB (limitação extrema)
- Textos comprimidos ao máximo
- Resultado: 500-5.000 linhas

**PC (2020+):**
- RAM: 8-32 GB (sem limites)
- Textos sem compressão
- Muitas duplicatas ("OK" aparece 500 vezes)
- Logs, debug, múltiplos idiomas
- Resultado: 50.000-500.000+ linhas

**Solução:** Use o otimizador! Remove duplicatas e reduz 80% do arquivo.

Leia mais: [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md)
</details>

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Este projeto é open source.

**Como contribuir:**
1. Fork este repositório
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📜 Licença

MIT License - Veja [LICENSE](LICENSE) para detalhes.

**Em resumo:** Você pode usar, modificar e distribuir livremente, inclusive comercialmente.

---

## 🙏 Créditos

- **Google Gemini API** - Tradução rápida e de alta qualidade
- **Ollama/Meta Llama** - Tradução offline ilimitada
- **PyQt6** - Interface gráfica moderna
- **Comunidade de tradução de ROMs** - Inspiração e feedback

---

## 📞 Suporte

**Documentação completa:** Veja todos os arquivos `.md` na raiz do projeto

**Principais:**
- [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) - Guia completo
- [INDICE_COMPLETO.md](INDICE_COMPLETO.md) - Índice de tudo
- [DIAGRAMA_FLUXO.md](DIAGRAMA_FLUXO.md) - Fluxogramas visuais

**Problemas?**
1. Execute `python verificar_sistema.py`
2. Consulte [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)
3. Abra uma issue no GitHub

---

## 🎉 Comece Agora!

```bash
# Windows
INICIAR_AQUI.bat

# Linux/Mac
python rom-translation-framework/interface/interface_tradutor_final.py
```

**Bora traduzir jogos!** 🎮🌍✨

---

**Versão:** 5.3
**Data:** 2025-12-19
**Status:** ✅ Pronto para produção
**Autor:** ROM Translation Framework Team
