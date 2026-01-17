# 🎯 IMPORTANTE: Jogos de PC - ATUALIZAÇÃO 2026!

## ⚠️ O Que Você Precisa Saber

**NOVIDADE:** Jogos de PC agora têm reinserção AUTOMÁTICA para `.exe`!

### ✅ Abas 1, 2 e 3 → FUNCIONAM para PC (.exe)!
- ✅ **Aba 1 (Extração)** → Extrai textos de `.exe`, `.dll`, `.wad`
- ✅ **Aba 2 (Tradução)** → Traduz para **15 idiomas** (Japonês→Russo, Chinês→Francês, etc.)
- ✅ **Aba 3 (Reinserção)** → **NOVO!** Reinsere automaticamente em `.exe`!

### ❌ Aba 4 (Lab. Gráfico) → NÃO funciona para PC!
- Motivo: Lab. Gráfico é só para tiles de ROMs (2bpp/4bpp)
- Para fontes de PC: Use FontForge ou editores `.ttf`

---

## ❓ Por Que é Diferente?

| **ROMs de Console** | **Jogos de PC** |
|---------------------|-----------------|
| ✅ Arquivo único (.smc, .nes, .gba) | ⚠️ Múltiplos arquivos (.exe, .wad, .pak, .dat) |
| ✅ Estrutura padronizada | ⚠️ Cada jogo é diferente |
| ✅ Tiles gráficos em formato 2bpp/4bpp | ⚠️ Fontes TrueType, PNG, sprites diversos |
| ✅ Reinserção automática (Aba 3) | ✅ **Reinserção automática para .exe!** (NOVO!) |

---

## 📝 COMO TRADUZIR JOGOS DE PC (Passo a Passo)

### ✅ PASSO 1: Extração (Funciona Normal!)
1. Vá para **Aba 1: Extração**
2. Em "Plataforma", selecione: **PC Games (Windows)**
3. Clique em "Selecionar ROM" e escolha o arquivo do jogo:
   - `.exe` (executável do jogo)
   - `.dll` (bibliotecas)
   - `.wad` (arquivos Doom/Quake)
   - `.pak` (arquivos compactados)
   - `.dat` (arquivos de dados)
   - `.txt` (arquivos de script)
4. Clique em **"Extrair Textos"**
5. ✅ Arquivo `nome_do_jogo_extracted.txt` criado!

### ✅ PASSO 2: Tradução (Funciona Normal!)
1. Vá para **Aba 2: Tradução**
2. Selecione o arquivo `*_optimized.txt`
3. **Configure idiomas:**
   - **Idioma Origem:** AUTO-DETECTAR
   - **Idioma Destino:** Escolha entre 15 idiomas:
     - 🇧🇷 Português, 🇺🇸 English, 🇪🇸 Español, 🇫🇷 Français, 🇩🇪 Deutsch
     - 🇮🇹 Italiano, 🇯🇵 日本語, 🇰🇷 한국어, 🇨🇳 中文, 🇷🇺 Русский
     - 🇸🇦 العربية, 🇮🇳 हिन्दी, 🇹🇷 Türkçe, 🇵🇱 Polski, 🇳🇱 Nederlands
4. Clique em **"Traduzir com IA"**
5. ✅ Arquivo `nome_do_jogo_translated.txt` criado!

### ✅ PASSO 3: Reinserção (NOVO para .EXE!)

#### Para Executáveis Windows (.exe):
1. Vá para **Aba 3: Reinserção**
2. **Selecione a ROM Original:** Escolha o `.exe` original
3. **Selecione o Arquivo Traduzido:** Escolha o `*_translated.txt`
4. **Defina nome de saída:** Ex: `game_PTBR.exe`
5. Clique em **"Reinserir Traduções"**
6. ⏳ Aguarde (2-3 minutos para arquivos grandes)
7. ✅ **Concluído!** Arquivo traduzido criado!

**Recursos Automáticos:**
- 📊 Realocação inteligente de strings grandes
- 🔧 Expansão automática do arquivo quando necessário
- 📈 Estatísticas detalhadas (modificadas, realocadas, expansão)

#### Para Outros Jogos de PC (Unity, RPG Maker):
⚠️ Use conversores específicos:
- **Doom/ZDoom:** `python converter_zdoom_simples.py`
- **Unity:** Use ferramenta UABE
- **RPG Maker:** Edite JSON diretamente
- **Outros:** Consulte `MANUAL_JOGOS_PC.md`

---

## ⚠️ IMPORTANTE: Use Versões Originais!

### 🎯 Garantia de Qualidade:
- ✅ **MELHORES RESULTADOS:** Executáveis originais não modificados (versões inglesas recomendadas)
- ⚠️ **FUNCIONA MAS ARRISCADO:** Versões crackeadas/piratas podem crashar após tradução
- 📝 **ESTABILIDADE GARANTIDA:** Apenas para arquivos originais

**Por quê?**
- Versões piratas têm proteções anti-tamper
- Dependências DLL podem estar corrompidas
- Nosso sistema foi otimizado para arquivos originais

---

## 💡 RESUMO RÁPIDO

| Etapa | ROMs Console | PC (.exe) | PC (Outros) |
|-------|--------------|-----------|-------------|
| **Aba 1 (Extração)** | ✅ Funciona | ✅ Funciona | ✅ Funciona |
| **Aba 2 (Tradução)** | ✅ Funciona | ✅ Funciona | ✅ Funciona |
| **Aba 3 (Reinserção)** | ✅ Automática | ✅ **AUTOMÁTICA!** (NOVO!) | ⚠️ Manual |
| **Aba 4 (Lab. Gráfico)** | ✅ Funciona | ❌ Não funciona | ❌ Não funciona |

---

## 📚 DOCUMENTAÇÃO COMPLETA

Para guias detalhados, consulte:
- 📘 **GUIA_PC_GAMES_ATUALIZADO.md** - Guia completo com FAQ
- 📘 **MANUAL_JOGOS_PC.md** - Referência técnica
- 📘 **FAQ_CLIENTES.md** - Perguntas frequentes

---

**Atualizado:** Janeiro 2026
**Versão:** 5.3 (Reinserção PC Automática)
