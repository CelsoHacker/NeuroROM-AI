# 🎯 GUIA: Tradução de Jogos de PC - ATUALIZADO 2026

## ✅ NOVIDADE: Reinserção Automática para PC AGORA DISPONÍVEL!

**O que mudou?**
- ✅ **Abas 1, 2 e 3 agora funcionam para PC!**
- ✅ Reinserção automática para arquivos `.exe` (Windows)
- ✅ Realocação inteligente de strings quando necessário
- ⚠️ Aba 4 (Laboratório Gráfico) ainda é só para ROMs

---

## 🎮 O Que Você Precisa Saber

### ✅ FUNCIONAM para Jogos de PC:
- **Aba 1 (Extração)** → ✅ Extrai textos de `.exe`, `.dll`, `.wad`, `.dat`
- **Aba 2 (Tradução)** → ✅ Traduz para qualquer idioma
- **Aba 3 (Reinserção)** → ✅ **NOVO!** Reinsere em `.exe` automaticamente

### ❌ NÃO FUNCIONA para Jogos de PC:
- **Aba 4 (Laboratório Gráfico)** → Só para ROMs de console (tiles 2bpp/4bpp)

---

## 📋 PASSO A PASSO COMPLETO

### ✅ PASSO 1: Extração

1. Abra a **Aba 1: Extração**
2. Em "Plataforma", selecione: **PC Games (Windows)**
3. Clique em "Selecionar ROM" e escolha o `.exe` do jogo
4. Clique em **"Extrair Textos"**
5. ✅ Arquivo `nome_do_jogo_extracted.txt` criado!

**Tipos de arquivo suportados:**
- `.exe` - Executáveis Windows
- `.dll` - Bibliotecas dinâmicas
- `.wad` - Doom/Quake
- `.pak` - Quake/Half-Life
- `.dat` - Arquivos de dados

---

### ✅ PASSO 2: Tradução

1. Vá para **Aba 2: Tradução**
2. Selecione o arquivo `*_optimized.txt`
3. **Configure idiomas:**
   - **Idioma Origem:** AUTO-DETECTAR (ou selecione: Inglês, Japonês, Russo, etc.)
   - **Idioma Destino:** Escolha qualquer um dos 15 idiomas disponíveis:
     - 🇧🇷 Português (Brasil)
     - 🇺🇸 English (US)
     - 🇪🇸 Español (España)
     - 🇫🇷 Français (France)
     - 🇩🇪 Deutsch (Deutschland)
     - 🇮🇹 Italiano (Italia)
     - 🇯🇵 日本語 (Japanese)
     - 🇰🇷 한국어 (Korean)
     - 🇨🇳 中文 (Chinese)
     - 🇷🇺 Русский (Russian)
     - 🇸🇦 العربية (Arabic)
     - 🇮🇳 हिन्दी (Hindi)
     - 🇹🇷 Türkçe (Turkish)
     - 🇵🇱 Polski (Polish)
     - 🇳🇱 Nederlands (Dutch)

4. Escolha o **Modo de Tradução:**
   - 🤖 Auto (Gemini → Ollama)
   - ⚡ Online Gemini (Google API)
   - 🖥️ Offline Ollama

5. Clique em **"Traduzir com IA"**
6. ✅ Arquivo `nome_do_jogo_translated.txt` gerado!

---

### ✅ PASSO 3: Reinserção (NOVO!)

1. Vá para **Aba 3: Reinserção**
2. **Selecione a ROM Original:**
   - Escolha o arquivo `.exe` original do jogo
   - Placeholder atualiza automaticamente: "Ex: DarkStone_PTBR.exe"

3. **Selecione o Arquivo Traduzido:**
   - Escolha o `*_translated.txt` gerado no Passo 2

4. **Defina nome do arquivo de saída:**
   - Por padrão: `nome_do_jogo_PTBR.exe`
   - Você pode alterar

5. Clique em **"Reinserir Traduções"**

6. ⏳ **Aguarde o processo:**
   - Barra de progresso mostra status
   - Log mostra:
     - Strings modificadas
     - Strings realocadas (quando tradução é maior)
     - Expansão do arquivo (em bytes)

7. ✅ **Concluído!** Arquivo traduzido criado!

---

## 🔧 COMO FUNCIONA A REINSERÇÃO AUTOMÁTICA

### Sistema Inteligente de Realocação:

1. **String CABE no espaço original?**
   - ✅ **SIM** → Substitui in-place com padding `0x00`
   - ❌ **NÃO** → Realoca automaticamente!

2. **Realocação Automática:**
   - String movida para o final do arquivo
   - Espaço antigo preenchido com `0x00`
   - Arquivo expandido quando necessário
   - **Performance otimizada:** ~2-3 minutos para arquivos de 500 MB

3. **Estatísticas mostradas:**
   ```
   📊 Estatísticas:
   • Total: 1208 strings
   • Modificadas: 850
   • Realocadas: 358
   • Expansão: +127,584 bytes
   ```

---

## ⚠️ IMPORTANTE: Use Versões Originais!

### 🎯 Garantia de Qualidade:

- ✅ **MELHORES RESULTADOS:** Executáveis originais não modificados
- ⚠️ **FUNCIONA MAS ARRISCADO:** Versões crackeadas/piratas podem crashar
- 📝 **ESTABILIDADE GARANTIDA:** Apenas para arquivos originais

**Por quê?**
- Versões piratas têm proteções anti-tamper
- Dependências DLL podem estar corrompidas
- Manifesto embutido pode estar alterado

---

## 🎮 JOGOS DE PC TESTADOS

| Jogo/Tipo | Status | Notas |
|-----------|--------|-------|
| Executáveis Windows antigos (1990-2010) | ✅ Funciona | Melhor compatibilidade |
| DarkStone (versão inglesa) | ✅ Testado | 504 MB, 1208 strings |
| Jogos Unity modernos | ⚠️ Use ferramentas específicas | UABE recomendado |
| RPG Maker MV/MZ | ⚠️ Manual | Edite JSON diretamente |

---

## ❓ FAQ - Perguntas Frequentes

### P: "Por que a Aba 4 (Lab. Gráfico) não funciona para PC?"
**R:** O Laboratório Gráfico foi projetado para tiles gráficos de ROMs (formato 2bpp/4bpp). Jogos de PC usam fontes TrueType (.ttf), PNG, sprites diversos. Use editores de fonte específicos como FontForge.

### P: "O executável traduzido não abre!"
**R:** Verifique:
1. É versão original ou crackeada? (Crackeadas podem crashar)
2. Instale Visual C++ Redistributable (2005, 2008, 2010)
3. Teste com versão original inglesa do jogo

### P: "Posso traduzir entre quaisquer idiomas?"
**R:** SIM! O sistema suporta **15 idiomas** em **qualquer combinação**:
- Japonês → Russo ✅
- Chinês → Francês ✅
- Coreano → Árabe ✅
- E todas as 225 combinações possíveis!

### P: "O arquivo ficou muito maior!"
**R:** Normal! Strings realocadas são adicionadas ao final do arquivo. Isso é esperado e não afeta o funcionamento do jogo.

---

## 📊 RESUMO VISUAL

```
╔═══════════════════════════════════════════════════════╗
║  TRADUÇÃO DE JOGOS DE PC - WORKFLOW COMPLETO          ║
╠═══════════════════════════════════════════════════════╣
║                                                        ║
║  📁 game.exe (original)                               ║
║       ↓                                               ║
║  [Aba 1] Extração                                     ║
║       ↓                                               ║
║  📄 game_extracted.txt                                ║
║       ↓                                               ║
║  [Aba 2] Tradução (🇯🇵→🇧🇷, 🇨🇳→🇫🇷, etc.)           ║
║       ↓                                               ║
║  📄 game_translated.txt                               ║
║       ↓                                               ║
║  [Aba 3] Reinserção AUTOMÁTICA ✨                     ║
║       ↓                                               ║
║  📁 game_PTBR.exe (traduzido!) 🎉                     ║
║                                                        ║
╚═══════════════════════════════════════════════════════╝
```

---

## 🚀 PRONTO PARA COMEÇAR!

1. Prepare o arquivo `.exe` original do jogo
2. Siga os 3 passos (Extração → Tradução → Reinserção)
3. Teste o jogo traduzido
4. Aproveite! 🎮

---

**Atualizado:** Janeiro 2026
**Versão:** 5.3 (Reinserção PC Automática)
**Autor:** ROM Translation Framework Team
