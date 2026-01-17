# 💻 MANUAL: Como Traduzir Jogos de PC

**ROM Translation Framework v5 - Guia Completo para Jogos de PC**

---

## 🎯 DIFERENÇA FUNDAMENTAL

### ❓ O Framework Traduz Jogos de PC?

**SIM!** O framework traduz **qualquer tipo de jogo**:
- ✅ ROMs de Console (SNES, NES, GBA, N64...)
- ✅ Jogos de PC (Doom, Quake, jogos antigos...)
- ✅ Arquivos de texto em geral

### ✅ ATUALIZAÇÃO 2026: Reinserção Automática para PC Disponível!

| Tipo | Extração | Tradução | Reinserção |
|------|----------|----------|------------|
| **ROMs de Console** | ✅ Auto | ✅ Auto | ✅ **Aba "3. Reinserção"** |
| **Jogos de PC (.exe)** | ✅ Auto | ✅ Auto | ✅ **Aba "3. Reinserção"** (**NOVO!**) |
| **Outros PC (Unity, RPG Maker)** | ✅ Auto | ✅ Auto | ⚠️ **Processo Manual** (veja abaixo) |

---

## 📋 COMO FUNCIONA PARA JOGOS DE PC

### PASSO 1: Extração de Textos ✅ (Funciona Normal)

1. Abra a **aba "1. Extração"**
2. Selecione o arquivo do jogo de PC:
   - `.exe` (executável)
   - `.wad` (Doom/Quake)
   - `.pak` (Quake/Half-Life)
   - `.dat` (diversos jogos)
   - `.txt` (arquivos de script)
3. Clique em **"Extrair Textos"**
4. ✅ Textos extraídos com sucesso!

### PASSO 2: Tradução ✅ (Funciona Normal)

1. Abra a **aba "2. Tradução"**
2. Selecione o arquivo `_optimized.txt` gerado
3. Configure idioma: Português (PT-BR)
4. Escolha o modo de tradução (Online ou Offline)
5. Clique em **"Traduzir com IA"**
6. ✅ Tradução concluída! → Arquivo `_translated.txt` gerado

### PASSO 3: Reinserção ✅ (AGORA FUNCIONA PARA .EXE!)

**✨ NOVIDADE 2026**: A aba "3. Reinserção" **AGORA FUNCIONA** para executáveis Windows (.exe)!

**Como usar:**
1. Vá para **Aba 3: Reinserção**
2. Selecione o `.exe` original do jogo
3. Selecione o arquivo `*_translated.txt`
4. Defina nome de saída (ex: `game_PTBR.exe`)
5. Clique em "Reinserir Traduções"
6. ✅ Processo automático com realocação inteligente!

**Funciona para:**
- ✅ Executáveis Windows (.exe, .dll) - **REINSERÇÃO AUTOMÁTICA**
- ⚠️ Jogos Unity, RPG Maker, etc. - Use conversores específicos (veja abaixo)

---

## 🎮 JOGOS DE PC SUPORTADOS

### 1. DOOM / DOOM II / Final Doom (ZDoom/GZDoom)

**Formato**: Arquivos `.wad` + Engine ZDoom/GZDoom

**Processo de Tradução**:

#### A) Extração e Tradução (Normal)
```
1. Extrair textos do .exe ou .wad
2. Traduzir na interface (Aba 2)
3. Gerar arquivo _translated.txt ✅
```

#### B) Conversão para ZDoom (Específico)
```bash
# Execute o conversor:
python converter_zdoom_simples.py

# Cole o caminho do arquivo _translated.txt quando solicitado

# Resultado: Doom_Traducao_PT-BR.pk3
```

#### C) Instalação no Jogo
```
1. Copie o arquivo .pk3 para a pasta do ZDoom
2. Inicie o jogo
3. Vá em: Options → Player Setup → Language
4. Selecione "Português (Brasil)"
5. Jogue em Português! 🎮
```

**Arquivos necessários**:
- ✅ ZDoom ou GZDoom instalado
- ✅ Arquivo DOOM.WAD ou DOOM2.WAD (jogo original)
- ✅ Arquivo `Doom_Traducao_PT-BR.pk3` (tradução gerada)

---

### 2. QUAKE / QUAKE II

**Formato**: Arquivos `.pak` contendo textos

**Processo de Tradução**:

#### A) Extração
```
1. Use o framework para extrair textos do .pak
2. OU extraia manualmente com PakScape/QuakeTools
3. Localize arquivos .txt dentro do .pak
```

#### B) Tradução
```
1. Use a Aba 2 para traduzir os arquivos .txt
2. Gere arquivos _translated.txt
```

#### C) Reinserção Manual
```
1. Abra o arquivo .pak com PakScape
2. Substitua os arquivos .txt originais pelos traduzidos
3. Salve o .pak modificado
4. Teste no jogo
```

**Ferramentas necessárias**:
- PakScape (editor de .pak)
- Quake Mod Tools

---

### 3. HALF-LIFE / Counter-Strike (GoldSrc)

**Formato**: Arquivos `.gcf` ou pasta `valve/resource/`

**Processo**:

#### A) Localização dos Textos
```
Half-Life/
├── valve/
│   └── resource/
│       ├── valve_english.txt    ← Textos em inglês
│       └── valve_portuguese.txt ← Criar este arquivo
```

#### B) Tradução
```
1. Extraia textos do valve_english.txt
2. Use a Aba 2 para traduzir
3. Renomeie _translated.txt para valve_portuguese.txt
```

#### C) Instalação
```
1. Copie valve_portuguese.txt para valve/resource/
2. No jogo, configure idioma: Português
3. Pronto!
```

---

### 4. JOGOS UNITY (Versões Antigas)

**Formato**: Arquivos `resources.assets` ou `sharedassets0.assets`

**Processo**:

#### A) Extração com UABE
```
1. Baixe Unity Assets Bundle Extractor (UABE)
2. Abra o arquivo .assets
3. Exporte os "TextAsset" para .txt
4. Use o framework para extrair/traduzir
```

#### B) Tradução
```
1. Traduza os arquivos .txt na Aba 2
2. Gere arquivos _translated.txt
```

#### C) Reinserção com UABE
```
1. Abra o .assets novamente no UABE
2. Importe os arquivos traduzidos
3. Salve o .assets modificado
4. Substitua no jogo
```

**Ferramentas**:
- Unity Assets Bundle Extractor (UABE)
- AssetStudio (alternativa)

---

### 5. RPG MAKER (MV/MZ)

**Formato**: Arquivos JSON em `www/data/`

**Processo**:

#### A) Localização
```
Game/
├── www/
│   └── data/
│       ├── Actors.json       ← Personagens
│       ├── Items.json        ← Itens
│       ├── Weapons.json      ← Armas
│       ├── Skills.json       ← Habilidades
│       ├── CommonEvents.json ← Diálogos
│       └── Map001.json       ← Mapas
```

#### B) Tradução
```
1. Use o framework para traduzir cada .json
2. Mantenha a estrutura JSON intacta
3. Traduza apenas os valores, não as chaves
```

#### C) Instalação
```
1. Substitua os arquivos .json originais
2. Teste o jogo
3. Se houver erros, verifique sintaxe JSON
```

**Ferramentas Recomendadas**:
- Translator++ (específico para RPG Maker)
- Ou use o framework + editor JSON manual

---

### 6. VISUAL NOVELS (RenPy)

**Formato**: Arquivos `.rpy` em `game/`

**Processo**:

#### A) Localização
```
VisualNovel/
├── game/
│   ├── script.rpy      ← Diálogos principais
│   ├── options.rpy     ← Opções
│   └── screens.rpy     ← Interface
```

#### B) Tradução
```
1. Extraia textos dos .rpy
2. Traduza na Aba 2 do framework
3. Reconstrua os arquivos .rpy com traduções
```

#### C) Criação de Patch
```
1. Crie pasta game/tl/portuguese/
2. Copie arquivos traduzidos para lá
3. RenPy carrega automaticamente
```

---

## 🛠️ CONVERSORES DISPONÍVEIS

O framework inclui conversores específicos para cada formato:

| Jogo/Engine | Conversor | Comando |
|-------------|-----------|---------|
| **ZDoom/GZDoom** | `converter_zdoom_simples.py` | `python converter_zdoom_simples.py` |
| **Quake** | `converter_quake.py` | *(em desenvolvimento)* |
| **Unity** | *(use UABE)* | - |
| **RPG Maker** | `converter_rpgmaker.py` | *(em desenvolvimento)* |
| **RenPy** | `converter_renpy.py` | *(em desenvolvimento)* |

---

## 📊 COMPARAÇÃO: ROMs vs JOGOS DE PC

| Aspecto | ROMs de Console | Jogos de PC |
|---------|----------------|-------------|
| **Arquivo** | Único (.smc, .nes) | Múltiplos (.exe, .wad, .pak) |
| **Estrutura** | Padronizada | Variável por jogo |
| **Extração** | ✅ Automática (Aba 1) | ✅ Automática (Aba 1) |
| **Tradução** | ✅ Automática (Aba 2) | ✅ Automática (Aba 2) |
| **Reinserção** | ✅ Automática (Aba 3) | ⚠️ Manual (conversor específico) |
| **Dificuldade** | ⭐ Fácil | ⭐⭐⭐ Intermediário |
| **Ferramentas Extras** | Nenhuma | Conversores/Editores específicos |

---

## 🎯 RESUMO PARA CLIENTES

### ✅ O Que Funciona Automaticamente:
1. **Extração de textos** de qualquer tipo de jogo (PC ou console)
2. **Tradução com IA** de qualquer arquivo de texto
3. **Reinserção automática** APENAS para ROMs de console

### ⚠️ O Que Requer Trabalho Manual:
1. **Reinserção em jogos de PC** (use conversores específicos)
2. **Testes no jogo** para validar tradução
3. **Ajustes finos** de textos que excedem limites de espaço

### 💡 Recomendação:
- **Para ROMs**: Use o fluxo completo (3 abas)
- **Para jogos de PC**: Use apenas Abas 1-2, depois conversor específico

---

## 📞 SUPORTE POR TIPO DE JOGO

### Clientes Perguntam: "Vocês Traduzem Jogos de PC?"

**Resposta**:
> "Sim! Traduzimos jogos de PC, mas o processo é um pouco diferente de ROMs de console.
>
> Para ROMs (SNES, GBA, etc): processo 100% automático em 3 cliques.
>
> Para jogos de PC: extração e tradução são automáticas, mas a aplicação da tradução no jogo requer um passo adicional com conversor específico.
>
> Jogos de PC suportados: Doom, Quake, Half-Life, Unity, RPG Maker, Visual Novels RenPy, entre outros."

### Preços Sugeridos

| Tipo de Tradução | Complexidade | Preço Sugerido |
|------------------|--------------|----------------|
| ROM de Console | Baixa | R$ 50-150 |
| Jogo PC Simples (Doom) | Média | R$ 100-250 |
| Jogo PC Complexo (Unity) | Alta | R$ 200-500 |
| Visual Novel | Média-Alta | R$ 150-400 |

*(Ajuste conforme seu mercado)*

---

## 🔧 TROUBLESHOOTING

### Problema: "Não consigo reinserir tradução em jogo de PC"

**Solução**:
- A aba "3. Reinserção" só funciona para ROMs de console
- Use o conversor específico do jogo (veja seção "Conversores")

### Problema: "Traduzi mas o jogo continua em inglês"

**Diagnóstico**:
1. Você aplicou a tradução? (executou o conversor?)
2. O arquivo está no local correto?
3. O jogo suporta múltiplos idiomas?

**Solução**: Consulte o guia específico do jogo acima

### Problema: "Textos aparecem cortados ou bugados"

**Causa**: Limite de espaço no jogo (tamanho máximo de caracteres)

**Solução**:
1. Abra o arquivo `_translated.txt`
2. Encurte manualmente os textos muito longos
3. Re-aplique a tradução

---

## 📚 RECURSOS ADICIONAIS

### Ferramentas Úteis para Jogos de PC:

| Ferramenta | Uso | Link |
|------------|-----|------|
| **SLADE** | Editor WAD (Doom) | [slade.mancubus.net](https://slade.mancubus.net/) |
| **UABE** | Editor Unity Assets | [github.com/SeriousCache/UABE](https://github.com/SeriousCache/UABE) |
| **PakScape** | Editor PAK (Quake) | [quakewiki.org](http://quakewiki.org/) |
| **Translator++** | RPG Maker/RenPy | [dreamsavior.net](https://dreamsavior.net/) |
| **RPA Extractor** | RenPy Archives | [github.com](https://github.com/) |

### Comunidades de Tradução:

- **ROMhacking.net**: ROMs de console
- **ZDoom Forums**: Doom/Hexen/Heretic
- **RPG Maker Forums**: Jogos RPG Maker
- **Lemma Soft Forums**: Visual Novels

---

## ✅ CHECKLIST PARA TRADUÇÃO DE JOGOS DE PC

```
[ ] 1. Identifique o engine/formato do jogo
[ ] 2. Extraia textos usando a Aba 1 do framework
[ ] 3. Traduza usando a Aba 2 do framework
[ ] 4. Identifique o conversor necessário (ou método manual)
[ ] 5. Execute o conversor específico
[ ] 6. Instale a tradução no jogo
[ ] 7. Teste extensivamente
[ ] 8. Ajuste textos cortados/bugados
[ ] 9. Teste novamente
[ ] 10. Entregue ao cliente com instruções de instalação
```

---

## 🎓 EXEMPLOS PRÁTICOS

### Exemplo 1: Cliente Quer Traduzir Doom (ZDoom)

**Fluxo Completo**:

```bash
# 1. Extração (Aba 1)
Arquivo: zdoom.exe
Saída: zdoom_optimized.txt ✅

# 2. Tradução (Aba 2)
Entrada: zdoom_optimized.txt
Modelo: Llama 3.1 8B (Offline)
Saída: zdoom_translated.txt ✅

# 3. Conversão (Terminal)
python converter_zdoom_simples.py
Entrada: zdoom_translated.txt
Saída: Doom_Traducao_PT-BR.pk3 ✅

# 4. Instalação (Manual do Cliente)
Copiar .pk3 para pasta do ZDoom
Configurar idioma no jogo
Jogar! 🎮
```

**Tempo estimado**: 30 minutos + tempo de tradução IA

---

### Exemplo 2: Cliente Quer Traduzir Visual Novel (RenPy)

**Fluxo Completo**:

```bash
# 1. Localização dos scripts
VisualNovel/game/script.rpy

# 2. Extração (Aba 1)
Arquivo: script.rpy
Saída: script_optimized.txt ✅

# 3. Tradução (Aba 2)
Saída: script_translated.txt ✅

# 4. Reconstrução Manual
- Criar arquivo script_ptbr.rpy
- Inserir traduções no formato RenPy
- Colocar em game/tl/portuguese/

# 5. Teste
Iniciar jogo
Selecionar Português
Validar diálogos
```

**Tempo estimado**: 1-2 horas + tradução IA

---

## 🏆 MELHORES PRÁTICAS

### Para Profissionais de Tradução:

1. **Sempre teste a tradução** antes de entregar ao cliente
2. **Documente o processo** para cada tipo de jogo
3. **Mantenha backups** dos arquivos originais
4. **Ajuste textos longos** que não cabem na interface
5. **Ofereça suporte pós-venda** para instalação

### Para Clientes:

1. **Faça backup** do jogo original antes de aplicar tradução
2. **Siga as instruções** de instalação cuidadosamente
3. **Reporte bugs** ao tradutor para correções
4. **Seja paciente** - tradução de jogos de PC é mais complexa que ROMs

---

## 📞 PRECISA DE AJUDA?

### Suporte Técnico:
- **GitHub**: [rom-translation-framework/issues](https://github.com/)
- **Email**: seu-email@exemplo.com
- **Discord**: Comunidade de Tradução

### Conversores Customizados:
Se você precisa traduzir um jogo de PC que não está neste manual, entre em contato! Podemos criar um conversor específico.

---

**ROM Translation Framework v5**
Desenvolvido por: Claude Sonnet 4.5
Última atualização: Dezembro 2024

🎮 **Traduza qualquer jogo - ROMs ou PC!** 🎮
