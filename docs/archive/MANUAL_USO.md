# NeuroROM AI - Universal Localization Suite v5.3 — Manual do Usuário

**Desenvolvido por:** Celso (Programador Solo)
**Email:** celsoexpert@gmail.com
**GitHub:** https://github.com/CelsoHacker/NeuroROM-AI
**Versão:** v5.3 Stable (Dezembro 2025)
**Licença:** Proprietária / Uso Profissional
**© 2025 All Rights Reserved**

---

## ⚖️ AVISO LEGAL IMPORTANTE

Esta ferramenta destina-se **exclusivamente** a:

✅ Tradução de ROMs/jogos que você **possui legalmente** (backup pessoal de cartuchos originais)
✅ Desenvolvimento de **homebrew** e conteúdo original
✅ **Preservação digital** de software em domínio público
✅ Fins **educacionais** e de pesquisa

**Você é responsável por garantir que possui os direitos legais sobre qualquer arquivo processado por esta ferramenta.** Não distribuímos, hospedamos ou facilitamos o download de conteúdo protegido por direitos autorais.

---

## 📋 ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Instalação e Requisitos](#2-instalação-e-requisitos)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Workflow Completo](#4-workflow-completo)
5. [Guia Passo a Passo](#5-guia-passo-a-passo)
6. [Configurações Avançadas](#6-configurações-avançadas)
7. [Troubleshooting](#7-troubleshooting)
8. [Perguntas Frequentes](#8-perguntas-frequentes)
9. [Especificações Técnicas](#9-especificações-técnicas)

---

## 1. VISÃO GERAL

### 1.1 O Que é o NeuroROM AI?

Sistema integrado para **tradução automatizada de jogos retro** através de pipeline modular com validação comercial:

```
ROM Original → Extração → Otimização → Tradução IA → Reinserção → ROM Traduzida
```

**Plataformas Suportadas (v5.3 Stable):**
- ✅ **Super Nintendo (SNES)** — 100% funcional
- ✅ **PlayStation 1 (PS1)** — 100% funcional
- ✅ **PC Games (Windows)** — 100% funcional
- 🚧 **Outras plataformas** — Roadmap disponível

### 1.2 Casos de Uso Reais

**Cenário 1: Tradução de Homebrew**
```
Input:  meu_jogo_snes.smc (jogo desenvolvido por você)
Output: meu_jogo_ptbr.smc (versão em português)
Tempo:  ~15 minutos para ROM de 2MB
```

**Cenário 2: Patch de Tradução**
```
Input:  backup_cartucho_original.bin (seu backup legal)
Output: jogo_traduzido.bin + arquivo_patch.ips
Tempo:  ~30 minutos para ROM de 8MB
```

### 1.3 Limitações Conhecidas

⚠️ **Não traduz automaticamente:**
- Gráficos com texto embutido (requer edição manual)
- Tabelas de caracteres customizadas (requer mapeamento prévio)
- Executáveis compactados sem descompressão prévia

---

## 2. INSTALAÇÃO E REQUISITOS

### 2.1 Requisitos de Sistema

**Hardware Mínimo:**
- CPU: Intel Core i3 ou equivalente (2+ cores)
- RAM: 4GB (8GB recomendado para ROMs grandes)
- Disco: 500MB livres + espaço para ROMs
- GPU: Não requerida (processamento em CPU)

**Software:**
- **Windows:** 10/11 (64-bit)
- **Python:** 3.10 ou superior
- **Bibliotecas:** PyQt6, requests, subprocess (incluídas)

### 2.2 Instalação Rápida

**Método 1: Executável Standalone (Recomendado)**
```bash
# Baixe o executável:
ROM_Universal_Translator_v5.2.exe

# Execute diretamente (sem instalação):
> ROM_Universal_Translator_v5.2.exe
```

**Método 2: Código Fonte Python**
```bash
# Clone ou extraia o repositório:
cd ROM_Universal_Translator

# Instale dependências:
pip install -r requirements.txt

# Execute:
python interface_tradutor.py
```

### 2.3 Estrutura de Diretórios

```
ROM_Universal_Translator/
├── interface_tradutor.py          # Interface principal
├── ROMs/                          # Coloque suas ROMs aqui
├── Scripts principais/            # Scripts de processamento
│   ├── text_extractor.py         # Extrator de textos
│   ├── text_cleaner.py           # Otimizador de dados
│   ├── translation_engine.py     # Motor de tradução
│   └── text_reinserter.py        # Reinseridor de traduções
├── extracted_texts.txt            # Output da extração
├── translated_texts.txt           # Output da tradução
└── translator_config.json         # Configurações persistentes
```

---

## 3. ARQUITETURA DO SISTEMA

### 3.1 Pipeline de Processamento

```
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: EXTRAÇÃO                                           │
│  ROM binária → Análise de padrões → extracted_texts.txt     │
│  - Detecção automática de encoding (Shift-JIS, UTF-8, etc) │
│  - Mapeamento de ponteiros de memória                       │
│  - Extração de strings com contexto                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: OTIMIZAÇÃO                                         │
│  Remoção de duplicatas, limpeza de caracteres de controle   │
│  - Deduplicação mantendo contexto                           │
│  - Preservação de variáveis de jogo (%s, {player}, etc)     │
│  - Análise de entropia para filtrar noise                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: TRADUÇÃO IA                                        │
│  optimized_texts.txt → API Translation → translated_texts   │
│  - Ollama local (offline, privado)                          │
│  - Google Gemini (online, alta qualidade)                   │
│  - DeepL API (online, contexto profissional)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 4: REINSERÇÃO                                         │
│  ROM original + traduções → ROM traduzida                   │
│  - Mapeamento de ponteiros preservado                       │
│  - Validação de tamanho (evita overflow)                    │
│  - Checksum recalculado automaticamente                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Tecnologias Utilizadas

**Frontend:**
- PyQt6 — Interface gráfica multi-plataforma
- QThread — Processamento assíncrono (UI não congela)
- QPalette — Gerenciamento de temas

**Backend:**
- subprocess.Popen — Execução de scripts de processamento
- threading — Operações paralelas de I/O
- regex — Análise de padrões textuais

**Integrações:**
- Ollama API — Tradução local via modelos LLM
- Google Gemini API — Tradução cloud de alta qualidade
- DeepL API — Tradução profissional contextual

---

## 4. WORKFLOW COMPLETO

### 4.1 Fluxo de Trabalho Típico

**Tempo total estimado:** 20-45 minutos (dependendo do tamanho da ROM)

```
[00:00] Iniciar aplicação
[00:30] Selecionar ROM e plataforma
[01:00] FASE 1: Extração (3-8 min)
[09:00] FASE 2: Otimização (1-2 min)
[11:00] FASE 3: Tradução (10-30 min, depende da API)
[41:00] FASE 4: Reinserção (2-5 min)
[46:00] Validação e teste da ROM traduzida
```

### 4.2 Decisões Críticas

**Escolha de API de Tradução:**

| API | Velocidade | Qualidade | Custo | Privacidade | Recomendação |
|-----|-----------|-----------|-------|-------------|--------------|
| **Ollama (Local)** | 🟡 Média | 🟡 Boa | ✅ Grátis | ✅ Total | Projetos pessoais |
| **Google Gemini** | ✅ Rápida | ✅ Excelente | 💰 Pago | ⚠️ Cloud | Qualidade profissional |
| **DeepL** | ✅ Rápida | ✅ Superior | 💰💰 Caro | ⚠️ Cloud | Traduções comerciais |

**Configuração de Workers:**
- **1-2 workers:** ROMs pequenas (<2MB), conexão lenta
- **3-5 workers:** Uso padrão (balanceamento ideal)
- **6-10 workers:** ROMs grandes (>10MB), conexão rápida, API sem rate limit

---

## 5. GUIA PASSO A PASSO

### 5.1 Primeira Execução

**PASSO 1: Configurar Idioma e Tema**

1. Execute `interface_tradutor.py`
2. Vá para aba **"Configurações"**
3. Configure:
   - **Idioma da Interface:** Escolha seu idioma preferido
   - **Tema Visual:** Preto/Cinza/Branco (escolha conforme preferência)
   - **Fonte da Interface:**
     - Use "Padrão" para suporte universal (Ocidente + Ásia)
     - Use fontes específicas se traduzir para CJK (Chinese/Japanese/Korean)

**PASSO 2: Preparar Ambiente de Trabalho**

```bash
# Crie diretório de trabalho:
mkdir C:\Traducoes\MeuJogo

# Copie sua ROM para a pasta ROMs:
copy meu_jogo.smc C:\ROM_Translator\ROMs\

# Certifique-se que os scripts estão presentes:
dir "C:\ROM_Translator\Scripts principais"
```

---

### 5.2 Extração de Textos (Aba 1)

**PASSO 3: Selecionar ROM**

1. Vá para aba **"1. Extração"**
2. **Plataforma:** Selecione a plataforma correta
   - ⚠️ Certifique-se que NÃO tem `[EM DESENVOLVIMENTO]` no nome
3. Clique **"Selecionar ROM"**
4. Navegue até sua ROM e confirme

**Status esperado:**
```
✅ ROM selecionada: meu_jogo.smc
   Arquivo ROM: meu_jogo.smc (verde, bold)
```

**PASSO 4: Extrair Textos**

1. Clique **"EXTRAIR TEXTOS"** (botão verde)
2. Monitore o progresso:
   ```
   [14:23:45] Starting extraction...
   [14:23:46] Analyzing binary structure...
   [14:24:12] Found 1,247 text strings
   [14:25:30] Extraction completed successfully
   ```
3. Aguarde até **"Done!"** no status
4. Botão **"🧹 OTIMIZAR DADOS"** será habilitado

**Output gerado:** `extracted_texts.txt` (na pasta raiz)

**PASSO 5: Otimizar Dados**

1. Clique **"🧹 OTIMIZAR DADOS"** (botão laranja)
2. Este processo:
   - Remove duplicatas (mantém contexto)
   - Limpa caracteres de controle
   - Filtra noise via análise de entropia
3. Aguarde conclusão (~1-2 minutos)

**Output gerado:** `optimized_texts.txt`

**Troubleshooting Extração:**

❌ **Erro: "No text strings found"**
```
Causa:   ROM compactada ou encoding não suportado
Solução: 1. Descompacte a ROM (use tool7z, WinRAR)
         2. Verifique se é realmente SNES/PS1
         3. Tente ajustar parâmetros no script extractor
```

❌ **Erro: "Permission denied"**
```
Causa:   ROM aberta em outro programa (emulador)
Solução: Feche todos os emuladores e tente novamente
```

---

### 5.3 Tradução (Aba 2)

**PASSO 6: Configurar Idiomas**

1. Vá para aba **"2. Tradução"**
2. Configure:
   - **Idioma de Origem (ROM):**
     - Use "AUTO-DETECTAR" se não souber
     - Ou selecione manualmente (Japonês, Inglês, etc)
   - **Idioma de Destino:** Escolha o idioma da tradução

**PASSO 7: Selecionar Modo de Tradução**

**Opção A: Ollama (Local, Gratuito)**
```
1. Modo de Tradução: "Offline (Ollama - Gemma 2B)"
2. Configuração de API: (oculto, não necessário)
3. Clique "TRADUZIR COM IA"
```

**Pré-requisito:** Ollama instalado e rodando
```bash
# Instalar Ollama:
> ollama pull gemma2:2b

# Verificar funcionamento:
> ollama run gemma2:2b "Translate to Portuguese: Hello"
```

**Opção B: Google Gemini (Cloud, Pago)**
```
1. Modo de Tradução: "Online Gemini (Google API)"
2. Configuração de API será exibida:
   - API Key: cole sua chave do Google AI Studio
   - Workers: 3-5 (padrão)
   - Timeout: 120s (padrão)
   - Cache: ✅ Habilitado (evita retradução)
3. Clique "TRADUZIR COM IA"
```

**Obter API Key Gemini:**
```
1. Acesse: https://makersuite.google.com/app/apikey
2. Clique "Create API Key"
3. Copie a chave (formato: AIza...)
4. Cole no campo "API Key"
```

**Opção C: DeepL (Cloud, Profissional)**
```
1. Modo de Tradução: "Online DeepL (API)"
2. API Key: cole sua chave DeepL
3. Mesmos parâmetros de Workers/Timeout
```

**PASSO 8: Executar Tradução**

1. Clique **"TRADUZIR COM IA"**
2. Progresso será exibido em tempo real:
   ```
   [14:30:15] Starting translation...
   [14:30:20] Processing chunk 1/47 (0%)
   [14:32:45] Processing chunk 23/47 (48%)
   [14:35:10] Processing chunk 47/47 (100%)
   [14:35:12] Translation completed successfully
   ```
3. **Tempo estimado:**
   - Ollama: 15-30 min (depende da CPU)
   - Gemini: 5-15 min (depende da rede)
   - DeepL: 3-10 min (mais rápido)

**Output gerado:** `translated_texts.txt`

**Troubleshooting Tradução:**

❌ **Erro: "API Key invalid"**
```
Causa:   Chave incorreta ou expirada
Solução: 1. Verifique se copiou a chave completa
         2. Regenere nova chave no portal da API
         3. Teste a chave com curl antes
```

❌ **Erro: "Rate limit exceeded"**
```
Causa:   Muitas requisições em pouco tempo
Solução: 1. Reduza Workers de 10 → 3
         2. Aumente Timeout de 120s → 180s
         3. Aguarde 1 minuto e tente novamente
```

❌ **Erro: "Ollama not responding"**
```
Causa:   Ollama não está rodando
Solução: 1. Abra terminal: ollama serve
         2. Aguarde "Listening on 127.0.0.1:11434"
         3. Tente tradução novamente
```

---

### 5.4 Reinserção (Aba 3)

**PASSO 9: Selecionar Arquivos**

1. Vá para aba **"3. Reinserção"**
2. **ROM Original:**
   - Clique "Selecionar ROM"
   - Escolha a ROM **original** (não modificada)
3. **Arquivo Traduzido:**
   - Clique "Selecionar Arquivo"
   - Escolha `translated_texts.txt` (gerado na etapa anterior)
4. **ROM Traduzida (Saída):**
   - Digite nome do output: `meu_jogo_PTBR.smc`

**PASSO 10: Reinserir Tradução**

1. Clique **"REINSERIR TRADUÇÃO"** (botão laranja)
2. Processo de reinserção:
   ```
   [14:40:00] Loading original ROM...
   [14:40:05] Mapping text pointers...
   [14:40:20] Inserting translations (1/1247)...
   [14:42:15] Recalculating checksum...
   [14:42:18] Writing output ROM...
   [14:42:20] Reinsertion completed successfully
   ```
3. Aguarde **"Done!"**

**Output final:** `meu_jogo_PTBR.smc` (ROM traduzida)

**PASSO 11: Validação**

1. **Teste em emulador:**
   ```bash
   # Abra a ROM traduzida:
   > snes9x meu_jogo_PTBR.smc

   # Verifique:
   ✅ Menus estão traduzidos?
   ✅ Diálogos estão traduzidos?
   ✅ Jogo carrega normalmente?
   ✅ Não há caracteres estranhos (□, �)?
   ```

2. **Compare checksums:**
   ```bash
   # Original:
   > certutil -hashfile meu_jogo.smc MD5

   # Traduzida:
   > certutil -hashfile meu_jogo_PTBR.smc MD5

   # Devem ser DIFERENTES (confirmando modificação)
   ```

**Troubleshooting Reinserção:**

❌ **Erro: "Text overflow detected"**
```
Causa:   Tradução maior que espaço disponível na ROM
Solução: 1. Edite translated_texts.txt manualmente
         2. Encurte textos muito longos
         3. Use abreviações quando possível
```

❌ **Erro: "Pointer mismatch"**
```
Causa:   ROM original foi modificada após extração
Solução: 1. Use MESMA ROM da extração
         2. Não edite a ROM entre extração e reinserção
         3. Recomece do PASSO 3
```

---

## 6. CONFIGURAÇÕES AVANÇADAS

### 6.1 Ajustes de Performance

**Para ROMs grandes (>10MB):**
```json
// translator_config.json
{
  "workers": 8,
  "timeout": 180,
  "chunk_size": 100,
  "use_cache": true
}
```

**Para conexões lentas:**
```json
{
  "workers": 2,
  "timeout": 300,
  "retry_attempts": 5
}
```

### 6.2 Customização de Fontes

**Fontes recomendadas por idioma:**

| Idioma de Destino | Fonte Recomendada |
|-------------------|-------------------|
| Português/Inglês/Espanhol | Segoe UI Semilight |
| Japonês | Yu Gothic UI |
| Coreano | Malgun Gothic |
| Chinês | Microsoft JhengHei UI |
| Árabe/Hindi | Padrão (fallback universal) |

**Aplicar fonte:**
1. Aba "Configurações"
2. "Fonte da Interface" → Selecione
3. Mudança é **instantânea** (sem reiniciar)

### 6.3 Temas Personalizados

**Editar temas manualmente:**
```python
# No código (interface_tradutor.py), localize:
THEMES = {
    "Meu Tema Custom": {
        "window": "#1a1a2e",
        "text": "#eee",
        "button": "#16213e",
        "accent": "#0f3460"
    }
}
```

---

## 7. TROUBLESHOOTING

### 7.1 Problemas Comuns

**PROBLEMA: UI congela durante operação**
```
Sintoma:  Janela fica branca, "Não está respondendo"
Causa:    Script de processamento travado
Solução:  1. Aguarde 2 minutos (pode ser carga temporária)
          2. Se persistir, feche pelo Task Manager
          3. Verifique logs em /tmp/translator.log
          4. Reporte o erro no GitHub Issues
```

**PROBLEMA: Tradução com caracteres estranhos (�, □)**
```
Sintoma:  Texto traduzido mostra símbolos em vez de letras
Causa:    Encoding incompatível ou falta de fonte
Solução:  1. Certifique-se que ROM usa UTF-8 ou Shift-JIS
          2. Instale fontes CJK no sistema
          3. Use "Fonte da Interface" → "Padrão"
          4. Reextraia com encoding correto
```

**PROBLEMA: Arquivo de saída vazio (0 bytes)**
```
Sintoma:  ROM traduzida gerada mas com 0KB
Causa:    Erro de escrita ou disco cheio
Solução:  1. Verifique espaço em disco (mín 50MB livres)
          2. Execute como Administrador
          3. Verifique permissões da pasta de saída
```

### 7.2 Logs e Diagnóstico

**Localização dos logs:**
```
Windows: C:\Users\[user]\AppData\Local\ROMTranslator\logs\
Linux:   ~/.local/share/ROMTranslator/logs/
Mac:     ~/Library/Application Support/ROMTranslator/logs/
```

**Habilitar modo debug:**
```python
# No início do interface_tradutor.py, adicione:
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Coletar informações para suporte:**
```bash
# Execute diagnóstico:
> python system_diagnostics.py

# Output:
System Information:
- OS: Windows 11 Pro 64-bit
- Python: 3.11.5
- PyQt6: 6.5.2
- RAM: 16GB (8GB available)
- Disk: 250GB free

Enviará: diagnostic_report.zip
```

---

## 8. PERGUNTAS FREQUENTES

**Q1: Posso traduzir ROMs comerciais que possuo fisicamente?**
```
R: Sim, desde que você possua o cartucho/disco original.
   Backup pessoal para uso próprio é geralmente permitido
   sob fair use em muitas jurisdições.
```

**Q2: A tradução preserva gráficos com texto?**
```
R: Não automaticamente. Gráficos (sprites, logos) requerem
   edição manual em ferramentas como Tile Molester ou GIMP.
```

**Q3: Posso usar o programa offline?**
```
R: Sim, com Ollama (modo offline). Gemini e DeepL requerem
   conexão à internet.
```

**Q4: Quanto custa usar as APIs de tradução?**
```
R: - Ollama: Grátis (local)
   - Gemini: $0.002/1K chars (~$2 por ROM média)
   - DeepL: $20/mês (500K chars) ou pay-as-you-go
```

**Q5: A ROM traduzida funciona em console real?**
```
R: Sim, desde que use flashcart compatível. Teste primeiro
   em emulador para validar a tradução.
```

**Q6: Posso distribuir a ROM traduzida?**
```
R: NÃO. Distribuir ROMs (mesmo traduzidas) viola copyright.
   Distribua apenas o PATCH (arquivo .ips/.bps) que outras
   pessoas aplicam em suas próprias ROMs legais.
```

**Q7: Como gerar um patch ao invés de ROM completa?**
```
R: Use ferramentas como Lunar IPS:
   1. Original ROM (clean)
   2. ROM traduzida
   3. Output: patch.ips (distribua apenas isto)
```

---

## 9. ESPECIFICAÇÕES TÉCNICAS

### 9.1 Formatos Suportados

**Entrada (ROMs):**
- `.smc`, `.sfc` (Super Nintendo)
- `.bin`, `.iso`, `.img` (PlayStation 1)
- `.z64`, `.n64`, `.v64` (Nintendo 64, futuro)
- `.gba` (Game Boy Advance, futuro)

**Saída (Textos):**
- `.txt` (UTF-8, Shift-JIS, ISO-8859-1)
- `.json` (estruturado com metadata)
- `.csv` (compatível com planilhas)

### 9.2 Encodings Suportados

| Encoding | Uso Comum | Detecção Automática |
|----------|-----------|---------------------|
| UTF-8 | Geral, moderno | ✅ Sim |
| Shift-JIS | Jogos japoneses (SNES, PS1) | ✅ Sim |
| EUC-JP | Alguns jogos japoneses antigos | ⚠️ Parcial |
| ISO-8859-1 | Jogos europeus (latin) | ✅ Sim |
| Windows-1252 | Jogos americanos | ✅ Sim |

### 9.3 Limitações de Tamanho

| Parâmetro | Mínimo | Máximo | Recomendado |
|-----------|--------|--------|-------------|
| Tamanho ROM | 512KB | 128MB | 1-16MB |
| Strings extraídas | 100 | 50,000 | 1,000-5,000 |
| Workers paralelos | 1 | 10 | 3-5 |
| Timeout API | 30s | 600s | 120s |

### 9.4 Compatibilidade de APIs

**Ollama:**
- Versão mínima: 0.1.0
- Modelos testados: gemma2:2b, llama3:8b, mistral:7b
- Requisito: 4GB RAM + 8GB VRAM (GPU) ou 16GB RAM (CPU)

**Google Gemini:**
- API version: v1
- Modelos: gemini-1.5-flash, gemini-1.5-pro
- Rate limit: 60 req/min (free), 1000 req/min (paid)

**DeepL:**
- API version: v2
- Línguas: 31+ idiomas
- Rate limit: 500K chars/mês (free), ilimitado (paid)

### 9.5 Dependências Python

```txt
PyQt6>=6.5.0
requests>=2.31.0
chardet>=5.2.0
numpy>=1.24.0
```

**Instalação completa:**
```bash
pip install PyQt6 requests chardet numpy
```

---

## 📞 SUPORTE E COMUNIDADE

**Reportar Bugs:**
- GitHub Issues: `https://github.com/seu-repo/issues`
- Email: `seu-email@exemplo.com`

**Contribuir:**
```bash
git clone https://github.com/seu-repo/rom-translator.git
cd rom-translator
git checkout -b feature/minha-melhoria
# Faça suas modificações
git push origin feature/minha-melhoria
# Abra Pull Request
```

**Documentação Adicional:**
- API Reference: `docs/API.md`
- Developer Guide: `docs/DEVELOPERS.md`
- Changelog: `CHANGELOG.md`

---

## 📝 CHANGELOG

**v5.2 (Dezembro 2024)**
- ✨ Adicionado seletor de fontes (suporte CJK)
- ✨ 15 idiomas de interface
- ✨ Platform status labels (`[EM DESENVOLVIMENTO]`)
- 🐛 Corrigido bug de troca de idioma
- 🐛 Corrigido restart em paths com espaços (Windows)
- ⚡ Threading otimizado (UI não congela)

**v5.1 (Novembro 2024)**
- ✨ Suporte a 3 APIs de tradução (Ollama, Gemini, DeepL)
- ✨ Sistema de temas (Preto, Cinza, Branco)
- 🐛 Corrigido memory leak no CleanerThread
- 🐛 Corrigido race condition no Ollama health check

**v5.0 (Outubro 2024)**
- 🎉 Release inicial
- ✨ Pipeline completo (extração → tradução → reinserção)
- ✨ Suporte SNES e PS1

---

## 📄 LICENÇA

**Uso Pessoal e Educacional Apenas**

Este software é fornecido "como está", sem garantias de qualquer tipo. O desenvolvedor não se responsabiliza por danos causados pelo uso inadequado ou violação de leis de copyright.

**Você concorda em:**
1. Usar apenas com conteúdo que você possui legalmente
2. Não distribuir ROMs traduzidas (apenas patches)
3. Respeitar direitos autorais dos desenvolvedores originais

**Copyright © 2025 Celso (Programador Solo). Todos os direitos reservados.**

---

*Manual gerado em: Dezembro 2025 | Versão: 5.2.0 | Última atualização: 08/12/2025*
