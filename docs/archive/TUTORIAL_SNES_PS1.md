# 🎮 Tutorial Prático: Traduzir SNES e PS1

> **Guia passo a passo para sua primeira tradução com o framework profissional!**

---

## 🎯 O QUE VOCÊ VAI FAZER

Traduzir completamente uma ROM de SNES ou PS1 do inglês para português, usando:
- ✅ Extração automática de textos
- ✅ Otimização (remove duplicatas)
- ✅ Tradução com IA (Modo Auto: Gemini + Ollama)
- ✅ Reinserção na ROM
- ✅ Teste no emulador

**Tempo total:** 10-30 minutos (dependendo do tamanho)

---

## 📋 PRÉ-REQUISITOS

### Você precisa ter:

✅ **Sistema instalado:**
```bash
python verificar_sistema.py
# Deve mostrar: ✅ EXCELENTE! Sistema pronto para usar!
```

✅ **Ollama rodando** (para modo offline ou fallback):
```bash
ollama serve  # Em outro terminal
```

✅ **API Key do Gemini** (opcional mas recomendado):
- Se não tiver, use apenas Ollama (mais lento mas funciona)

✅ **ROM legal:**
- Você deve possuir o jogo original
- ROM para backup pessoal

✅ **Emulador instalado:**
- **SNES:** Snes9x, ZSNES, bsnes
- **PS1:** ePSXe, DuckStation, PCSX-ReARMed

---

## 🚀 TUTORIAL 1: SUPER NINTENDO (SNES)

### Passo 1: Preparação (1 minuto)

1. **Organize seus arquivos:**
```
📁 Meu Projeto SNES/
  ├─ meu_jogo.smc          ← ROM original
  └─ (arquivos gerados aparecerão aqui)
```

2. **Abra a interface:**
```bash
# Windows
INICIAR_AQUI.bat
→ Opção [1] Abrir Interface

# Ou manualmente
python rom-translation-framework/interface/interface_tradutor_final.py
```

3. **Verifique configuração:**
- Plataforma: `Super Nintendo (SNES)` ✅ (já selecionado)
- Idioma destino: `Portuguese (Brazil)`

---

### Passo 2: Extração de Textos (30 segundos)

**Aba: "1. Extração e Otimização"**

1. **Selecione a ROM:**
   - Clique em **"Selecionar ROM"**
   - Navegue até `meu_jogo.smc`
   - Selecione e abra

2. **Extraia os textos:**
   - Clique em **"EXTRAIR TEXTOS"**
   - Aguarde: `Extraindo... 0% → 100%`
   - Status: `✅ Extração concluída!`

**Arquivo gerado:**
```
📁 Meu Projeto SNES/
  ├─ meu_jogo.smc
  └─ meu_jogo_extracted.txt  ← Textos extraídos! (~2.000-5.000 linhas)
```

**O que aconteceu:**
- Sistema escaneou ROM byte por byte
- Detectou strings ASCII (0x20-0x7E)
- Salvou textos com offsets (posição na ROM)
- Mínimo: 3 caracteres alfanuméricos

**Exemplo de conteúdo:**
```
0x1a2b: START GAME
0x1a45: OPTIONS
0x1a5f: CONTINUE
0x2f10: Press any button
0x3a21: You found a treasure!
```

---

### Passo 3: Otimização (5 segundos) - RECOMENDADO!

**Ainda na Aba 1:**

1. **Otimize o arquivo:**
   - Clique em **"OTIMIZAR ARQUIVO"**
   - Aguarde: `Otimizando...`
   - Status: `✅ Reduzido de 4.580 → 2.310 linhas (50% redução!)`

**Arquivo gerado:**
```
📁 Meu Projeto SNES/
  ├─ meu_jogo.smc
  ├─ meu_jogo_extracted.txt
  └─ meu_jogo_extracted_optimized.txt  ← Arquivo otimizado! (50% menor)
```

**Por que otimizar?**
- ROMs repetem muito texto ("OK", "CANCEL", "YES", "NO")
- Otimizador remove duplicatas
- **Economia:** 50% menos tempo de tradução!
- **Qualidade:** Mesma (só remove repetidos)

---

### Passo 4: Tradução com IA (2-10 minutos)

**Aba: "2. Tradução"**

1. **Configure o modo:**
   - **Modo de Tradução:** `🤖 Auto (Gemini → Ollama)` ✅
   - **API Key Gemini:** Cole sua key (ou deixe vazio para Ollama puro)
   - **Workers:** `3` ✅
   - **Timeout:** `120` segundos

2. **Carregue arquivo otimizado:**
   - O sistema já detectou: `meu_jogo_extracted_optimized.txt` ✅
   - Se não, clique em "Selecionar" e escolha o arquivo `_optimized.txt`

3. **Inicie a tradução:**
   - Clique em **"TRADUZIR COM IA"**

**O que acontece (Modo Auto):**

```
[00:00] 🤖 AUTO Mode: 2.310 linhas
[00:01] ✅ Gemini: Disponível
[00:01] ✅ Ollama: Disponível
[00:02] ⚡ Traduzindo com Gemini...
[00:05] ✅ Batch 1/12 completo (200 textos)
[00:10] ✅ Batch 2/12 completo (200 textos)
[00:15] ✅ Batch 3/12 completo (200 textos)
...
[01:30] ✅ Tradução completa!

📊 ESTATÍSTICAS:
   Gemini: 2.000 textos (1 min)
   Ollama: 310 textos (30s)
   Total: 2.310 textos (1m 30s)
```

**Se quota Gemini esgotar:**
```
[00:15] ⚠️ Erro: 429 Quota exceeded
[00:15] 🔄 Mudou para Ollama (quota Gemini esgotada)
[00:20] 🐌 Traduzindo com Ollama...
[05:00] ✅ Batch 12/12 completo
```

**Você pode:**
- ✅ Acompanhar progresso em tempo real
- ✅ Clicar **⏹️ PARAR** a qualquer momento (salva progresso!)
- ✅ Retomar depois (carrega de onde parou)

**Arquivo gerado:**
```
📁 Meu Projeto SNES/
  ├─ meu_jogo.smc
  ├─ meu_jogo_extracted.txt
  ├─ meu_jogo_extracted_optimized.txt
  └─ meu_jogo_extracted_optimized_traduzido.txt  ← TRADUÇÃO! 🎉
```

**Exemplo de resultado:**
```
0x1a2b: INICIAR JOGO
0x1a45: OPÇÕES
0x1a5f: CONTINUAR
0x2f10: Pressione qualquer botão
0x3a21: Você encontrou um tesouro!
```

---

### Passo 5: Reinserção na ROM (5 segundos)

**Aba: "3. Reinserção"**

1. **Selecione ROM original:**
   - Clique em **"Selecionar ROM"**
   - Escolha: `meu_jogo.smc`

2. **Arquivo traduzido:**
   - Sistema já detectou: `meu_jogo_extracted_optimized_traduzido.txt` ✅

3. **Nome da ROM traduzida:**
   - Digite: `meu_jogo_PTBR.smc`

4. **Reinsira:**
   - Clique em **"REINSERIR TRADUÇÕES"**
   - Aguarde: `Reinserindo... 0% → 100%`
   - Status: `✅ Reinserção concluída!`

**Arquivo final:**
```
📁 Meu Projeto SNES/
  ├─ meu_jogo.smc                                   ← Original (intacto)
  ├─ meu_jogo_extracted.txt
  ├─ meu_jogo_extracted_optimized.txt
  ├─ meu_jogo_extracted_optimized_traduzido.txt
  └─ meu_jogo_PTBR.smc  ← ROM TRADUZIDA! 🎉🇧🇷
```

**O que aconteceu:**
1. Sistema leu offsets do arquivo traduzido
2. Para cada offset, substituiu texto original pelo traduzido
3. Validou tamanhos (avisa se tradução maior que original)
4. Gerou nova ROM com traduções

---

### Passo 6: Teste no Emulador (1 minuto)

1. **Abra seu emulador SNES** (Snes9x, ZSNES, etc.)

2. **Carregue a ROM:**
   - File → Open → `meu_jogo_PTBR.smc`

3. **Verifique tradução:**
   - ✅ Menu em português?
   - ✅ Diálogos em português?
   - ✅ Jogo funciona normal?

**Se algo deu errado:**
- Texto cortado → Tradução maior que original (use palavras menores)
- Caracteres estranhos → Encoding incompatível (alguns jogos precisam tabela customizada)
- Jogo não abre → ROM corrompida (refaça extração e reinserção)

**Sucesso!** 🎉 Você traduziu sua primeira ROM SNES!

---

## 🎮 TUTORIAL 2: PLAYSTATION 1 (PS1)

### Diferenças vs SNES:

| Aspecto | SNES | PS1 |
|---------|------|-----|
| Tamanho ROM | 4MB | 700MB |
| Textos | 2k-5k | 10k-50k |
| Formato | .smc/.sfc | .iso/.bin |
| Extração | 10s | 30-60s |
| Otimização | 50% redução | **80% redução!** |
| Tradução | 2-10 min | 10-30 min |

**Resumo:** MESMO processo, só demora mais! ✅

---

### Passo 1: Preparação

```
📁 Meu Projeto PS1/
  ├─ meu_jogo.bin
  ├─ meu_jogo.cue  ← Arquivo descritor (opcional)
  └─ (arquivos gerados)
```

**Plataforma:** Selecione `PlayStation 1 (PS1)` no dropdown

---

### Passo 2: Extração (30-60 segundos)

**Mesmo processo que SNES:**
- Selecione: `meu_jogo.bin`
- Clique: **EXTRAIR TEXTOS**
- Aguarde: ~30-60s (arquivo grande)

**Arquivo gerado:**
```
meu_jogo_extracted.txt  (~20.000 linhas típico)
```

---

### Passo 3: Otimização (**CRÍTICO para PS1!**)

**PS1 tem MUITAS duplicatas!**

- Clique: **OTIMIZAR ARQUIVO**
- Resultado: `20.000 → 4.000 linhas` (80% redução!) 🚀

**Por quê?**
- Jogos PS1 repetem muito: menus, botões, UI
- Exemplos: "OK" aparece 500x, "CANCEL" 500x, etc.
- **SEM otimização:** 5 horas de tradução
- **COM otimização:** 30 minutos! ✨

---

### Passo 4: Tradução (10-30 minutos)

**Configuração:**
- Modo: `🤖 Auto` (Gemini até quota esgotar, depois Ollama)
- Workers: `3`
- Arquivo: `meu_jogo_extracted_optimized.txt`

**Clique:** TRADUZIR

**Exemplo real (4.000 linhas otimizadas):**
```
[00:00] 🤖 AUTO Mode: 4.000 linhas
[00:05] ⚡ Gemini: 200 linhas/batch
[02:00] ✅ Gemini: 4.000 linhas (2 min) - Usou 20 requisições
[02:00] ✅ Tradução completa!

OU (se quota esgotada):

[00:00] 🤖 AUTO Mode: 4.000 linhas
[00:05] ⚡ Gemini: Primeiros 4.000 textos
[02:00] ⚠️ Quota esgotada (usou 20/20)
[02:01] 🔄 Mudando para Ollama...
[02:01] 🐌 Ollama: Restantes (se houver mais batches)
[10:00] ✅ Tradução completa!
```

**Dica:** Para PS1, otimização é ESSENCIAL!

---

### Passo 5: Reinserção (20-40 segundos)

**Mesmo processo:**
1. Selecione ROM original: `meu_jogo.bin`
2. Arquivo traduzido: Auto-detectado
3. Nome saída: `meu_jogo_PTBR.bin`
4. Clique: **REINSERIR**

**Gera:**
```
meu_jogo_PTBR.bin  ← Nova ISO traduzida!
meu_jogo_PTBR.cue  ← Descritor (se necessário)
```

---

### Passo 6: Teste no Emulador

**Emuladores recomendados:**
- **DuckStation** (melhor compatibilidade)
- ePSXe
- PCSX-ReARMed

**Carregue:**
- File → Open Disc Image → `meu_jogo_PTBR.bin`

**Verifique:**
- Menus em português ✅
- Diálogos traduzidos ✅
- Jogo funciona normal ✅

---

## 🌡️ MONITORAMENTO (GPU e Progresso)

### Durante tradução, observe:

**Interface mostra:**
```
┌─────────────────────────────────────────────┐
│ Progresso: ████████░░░░░░░░░░ 40%          │
│ Status: ⚡ Traduzindo com Gemini...         │
│ Batch: 8/20                                 │
│ Modo: Gemini (Rápido)                       │
│ Textos: 1.600/4.000                         │
│ Tempo decorrido: 1m 20s                     │
│ Tempo estimado restante: 2m 5s              │
└─────────────────────────────────────────────┘
```

**GPU (se usar Ollama):**
```
nvidia-smi  # Em outro terminal

+-----------------------------------------------------------------------------+
| NVIDIA-SMI 555.85       Driver Version: 555.85       CUDA Version: 12.5     |
|-------------------------------+----------------------+----------------------+
| GPU  Name            TCC/WDDM | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ... WDDM  | 00000000:01:00.0  On |                  N/A |
| 30%   62C    P2    65W / 120W |   3600MiB /  6144MiB |     85%      Default |
+-------------------------------+----------------------+----------------------+

Temperatura: 62°C ✅ (seguro até 80°C)
GPU: 85% (normal para Ollama)
VRAM: 3.6GB/6GB (58%)
```

**Se temperatura > 75°C:**
1. Clique ⏹️ **PARAR**
2. Aguarde 30 minutos (GPU esfriar)
3. Retome tradução (carrega de onde parou)

---

## 📊 ESTIMATIVAS REALISTAS

### SNES (2.310 linhas otimizadas)

| Etapa | Tempo | Resultado |
|-------|-------|-----------|
| Extração | 10s | 4.580 linhas |
| Otimização | 5s | 2.310 linhas (-50%) |
| Tradução (Gemini) | 1m 30s | 2.310 linhas traduzidas |
| Reinserção | 5s | ROM traduzida |
| **TOTAL** | **~2 minutos** | ✅ Pronto! |

### PS1 (4.000 linhas otimizadas)

| Etapa | Tempo | Resultado |
|-------|-------|-----------|
| Extração | 45s | 20.000 linhas |
| Otimização | 10s | 4.000 linhas (-80%!) |
| Tradução (Auto) | 10-15 min | 4.000 traduzidas |
| Reinserção | 30s | ISO traduzida |
| **TOTAL** | **~13 minutos** | ✅ Pronto! |

---

## 🎯 CHECKLIST DE SUCESSO

### Antes de começar:
- [ ] Sistema verificado (`python verificar_sistema.py`)
- [ ] Ollama rodando (`ollama serve`)
- [ ] API Key Gemini (opcional)
- [ ] ROM legal (você possui o jogo)
- [ ] Emulador instalado

### Durante tradução:
- [ ] Modo Auto selecionado
- [ ] Workers: 3
- [ ] Arquivo otimizado carregado
- [ ] Monitorando temperatura (se Ollama)

### Após tradução:
- [ ] ROM traduzida gerada
- [ ] Testada no emulador
- [ ] Funciona corretamente
- [ ] Textos legíveis
- [ ] Sem crashes

---

## ❓ PROBLEMAS COMUNS E SOLUÇÕES

### Extração

**Problema:** "Extração falhou"
- ✅ **Solução:** Verifique formato da ROM (.smc, .sfc, .bin, .iso)

**Problema:** "Poucos textos extraídos"
- ✅ **Solução:** Jogo pode usar encoding especial ou compressão

### Tradução

**Problema:** "API Key inválida"
- ✅ **Solução:** Verifique se API Key está correta (Google AI Studio)

**Problema:** "Quota exceeded"
- ✅ **Solução:** Sistema muda para Ollama automaticamente (modo Auto)

**Problema:** "Muito lento"
- ✅ **Solução:** Use Gemini ou otimize arquivo primeiro

### Reinserção

**Problema:** "Texto cortado no jogo"
- ✅ **Solução:** Tradução maior que original. Use palavras menores.

**Problema:** "Caracteres estranhos"
- ✅ **Solução:** Encoding incompatível. Alguns jogos precisam tabela custom.

**Problema:** "ROM não abre"
- ✅ **Solução:** Refaça processo desde extração

---

## 🎓 PRÓXIMOS PASSOS

### Após dominar SNES e PS1:

1. **Experimente NES** (similar a SNES, mais simples)
2. **Tente GBA** (Game Boy Advance, médio)
3. **Desafie-se com N64** (complexo, textures + strings)
4. **Contribua** melhorias para o framework!

### Aprenda mais:

- [STATUS_PLATAFORMAS.md](STATUS_PLATAFORMAS.md) - Todas as plataformas
- [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) - Guia completo
- [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md) - GPU e temperatura

---

## 🎉 PARABÉNS!

Você agora sabe traduzir ROMs profissionalmente usando:
- ✅ Extração automática
- ✅ Otimização inteligente
- ✅ IA com fallback (Gemini + Ollama)
- ✅ Gerenciamento de quota
- ✅ Controle total (botão PARAR)
- ✅ Reinserção automática

**Você está pronto para traduzir jogos!** 🎮🌍✨

**Bora testar?** Escolha uma ROM e comece agora! 🚀

---

**Versão:** ROM Translation Framework v5.3
**Data:** 2025-12-19
**Autor:** Celso (Programador Solo)
**Status:** ✅ TUTORIAL COMPLETO E TESTADO
