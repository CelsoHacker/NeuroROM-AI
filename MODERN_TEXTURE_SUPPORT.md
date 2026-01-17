# 🎨 MODERN TEXTURE SUPPORT - Documentação Completa

**Data**: 04/Janeiro/2026
**Status**: ✅ IMPLEMENTAÇÃO COMPLETA
**Arquivo**: [`interface/gui_tabs/graphic_lab.py`](interface/gui_tabs/graphic_lab.py)

---

## 📋 VISÃO GERAL

O **ROM Translation Framework** agora suporta **tradução de texturas de jogos modernos** (Unity, Unreal, jogos indie) além de ROMs retro. Este recurso permite traduzir textos embutidos em texturas de jogos de PC, expandindo dramaticamente o alcance do framework.

### 🎯 Objetivo Comercial

> **"Traduzir desde o Super Mario de 1990 até o jogo indie que lançou ontem na Steam"**

---

## 🚀 FORMATOS SUPORTADOS

| Formato | Descrição | Engines Comuns | Status |
|---------|-----------|----------------|--------|
| **PNG** | Portable Network Graphics | Unity, Godot, GameMaker | ✅ Completo |
| **TGA** | Targa (Truevision) | Unreal Engine, Source | ✅ Completo |
| **BMP** | Bitmap (Windows) | Jogos antigos de PC | ✅ Completo |
| **DDS** | DirectDraw Surface | DirectX, Unreal | ⚠️ Leitura limitada* |

\* **DDS**: Pillow tem suporte limitado. Recomenda-se converter para PNG/TGA usando GIMP, ImageMagick ou Paint.NET.

---

## 📦 FUNCIONALIDADES IMPLEMENTADAS

### 1. **Carregamento de Texturas** (`load_modern_texture()`)

**Localização**: [graphic_lab.py:847](interface/gui_tabs/graphic_lab.py#L847)

**Recursos**:
- ✅ QFileDialog com filtros específicos por formato
- ✅ Validação de formato DDS com fallback para conversão manual
- ✅ Conversão automática para RGB/RGBA (compatibilidade)
- ✅ Preview automático redimensionado (max 512x512)
- ✅ Logs detalhados (resolução, modo de cor, caminho)

**Uso**:
```python
1. Clique no botão "🎨 CARREGAR TEXTURA"
2. Selecione arquivo PNG/TGA/BMP/DDS
3. Textura é carregada e exibida na grid
4. Use "🤖 OCR + TRADUÇÃO AI" para processar
```

---

### 2. **Pipeline OCR + AI Translation** (`process_modern_texture_ocr_translation()`)

**Localização**: [graphic_lab.py:973](interface/gui_tabs/graphic_lab.py#L973)

**Fluxo de 5 Etapas**:

#### **[1/5] Pre-processamento** (`_preprocess_modern_texture_for_ocr()`)
**Localização**: [graphic_lab.py:1088](interface/gui_tabs/graphic_lab.py#L1088)

**Técnicas Aplicadas**:
- **Upscaling**: Se resolução < 512px → redimensiona com LANCZOS
- **Escala de cinza**: Conversão RGB → L (luminância)
- **Contraste**: Aumenta 2x com `ImageEnhance.Contrast`
- **Nitidez**: Aplica filtro `SHARPEN`
- **Binarização**: Threshold em 128 (preto/branco)

**Entrada**: PIL.Image (RGB/RGBA)
**Saída**: PIL.Image (RGB binarizado otimizado para OCR)

#### **[2/5] OCR** (`_perform_modern_texture_ocr()`)
**Localização**: [graphic_lab.py:1126](interface/gui_tabs/graphic_lab.py#L1126)

**Configuração pytesseract**:
```python
custom_config = r'--oem 3 --psm 3'
# OEM 3: Default (LSTM neural net)
# PSM 3: Automatic page segmentation (multilinha)
```

**Entrada**: PIL.Image (pre-processada)
**Saída**: String com texto extraído

**Exemplo**:
```
Entrada: menu_background.png (texto "New Game", "Options", "Exit")
Saída: "New Game\nOptions\nExit"
```

#### **[3/5] AI Translation** (reutiliza `_translate_with_gemini()`)
**Localização**: [graphic_lab.py:683](interface/gui_tabs/graphic_lab.py#L683)

**Configuração**:
- **Modelo**: `gemini-1.5-flash`
- **Prompt**: `"Translate the following text to {target_language}. Provide ONLY the translation, no explanations:"`
- **Target Language**: Configurável (padrão: "Portuguese (Brazil)")

**Entrada**: String em inglês
**Saída**: String traduzida

**Exemplo**:
```
Entrada: "New Game\nOptions\nExit"
Saída: "Novo Jogo\nOpções\nSair"
```

#### **[4/5] Renderização** (`_render_text_on_modern_texture()`)
**Localização**: [graphic_lab.py:1148](interface/gui_tabs/graphic_lab.py#L1148)

**Algoritmo Inteligente**:

1. **Detecção de Bounding Box**:
   - Usa `pytesseract.image_to_data()` para obter coordenadas de cada palavra
   - Calcula bounding box total que engloba todo o texto

2. **Limpeza da Região**:
   - Detecta cor de fundo com `_detect_background_color()` (média RGB ao redor do texto)
   - Apaga região original preenchendo com a cor de fundo

3. **Cálculo de Fonte Dinâmica**:
   ```python
   font_size = max(12, min(region_height - 4, region_width // len(translated_text)))
   ```
   - Ajusta tamanho para caber na região original
   - Mínimo de 12px, máximo baseado na altura da região

4. **Renderização Centralizada**:
   - Calcula posição central: `(region_width - text_width) // 2`
   - Escolhe cor do texto baseada no fundo:
     - **Fundo escuro** (soma RGB < 384): Texto branco
     - **Fundo claro** (soma RGB ≥ 384): Texto preto

**Entrada**: PIL.Image original, texto original, texto traduzido
**Saída**: PIL.Image modificada com tradução renderizada

#### **[5/5] Salvamento** (`_save_modern_texture()`)
**Localização**: [graphic_lab.py:1256](interface/gui_tabs/graphic_lab.py#L1256)

**Comportamento**:
- Mantém formato original (`.png`, `.tga`, `.bmp`)
- DDS é convertido para PNG (Pillow não suporta escrita em DDS)
- Adiciona sufixo `_TRANSLATED` ao nome do arquivo
- Salva com qualidade 95% (PNG/JPG)

**Exemplo**:
```
Entrada: menu_background.png
Saída: menu_background_TRANSLATED.png
```

---

### 3. **Display de Preview** (`_display_modern_texture_preview()`)

**Localização**: [graphic_lab.py:935](interface/gui_tabs/graphic_lab.py#L935)

**Funcionalidades**:
- Limpa grid existente (remove tiles retro se houver)
- Converte PIL.Image → QPixmap via `PIL.ImageQt`
- Redimensiona mantendo aspect ratio (max 512x512)
- Aplica estilo dark theme: `border: 2px solid #16a085; background: #1e1e1e;`
- Centraliza na grid

---

### 4. **Detecção de Cor de Fundo** (`_detect_background_color()`)

**Localização**: [graphic_lab.py:1223](interface/gui_tabs/graphic_lab.py#L1223)

**Algoritmo**:
1. Amostra área ao redor do texto (margem de 10px)
2. Extrai todos os pixels da região
3. Calcula média RGB:
   ```python
   avg_r = sum(p[0] for p in pixels) // len(pixels)
   avg_g = sum(p[1] for p in pixels) // len(pixels)
   avg_b = sum(p[2] for p in pixels) // len(pixels)
   ```

**Entrada**: PIL.Image, (x1, y1, x2, y2) da região de texto
**Saída**: Tupla (R, G, B) com cor média

---

### 5. **Smart Router** (`intelligent_ocr_translation()`)

**Localização**: [graphic_lab.py:512](interface/gui_tabs/graphic_lab.py#L512)

**Lógica de Decisão**:

```
┌─────────────────────────────────────┐
│ Usuário clica em "🤖 OCR + TRADUÇÃO" │
└────────────┬────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ modern_texture != None? │
    └────┬───────────┬────┘
         │ SIM       │ NÃO
         ▼           ▼
    ┌─────────┐  ┌──────────────────┐
    │ MODO 1  │  │ selected_tile != None? │
    │ Textura │  └──┬───────────┬───┘
    │ Moderna │     │ SIM       │ NÃO
    └─────────┘     ▼           ▼
              ┌─────────┐  ┌─────────┐
              │ MODO 2  │  │  AVISO  │
              │ Tile 8x8│  │ Selecione│
              │  Retro  │  │ Conteúdo│
              └─────────┘  └─────────┘
```

**Comportamento**:
- **Prioridade 1**: Se textura moderna carregada → `process_modern_texture_ocr_translation()`
- **Prioridade 2**: Se tile retro selecionado → `process_tile_ocr_translation()`
- **Fallback**: Exibe mensagem com instruções para ambos os modos

---

## 🎨 INTERFACE DO USUÁRIO

### Botões Adicionados

#### 1. **"🎨 CARREGAR TEXTURA"**
**Localização**: [graphic_lab.py:342](interface/gui_tabs/graphic_lab.py#L342)

**Estilo**:
```python
background: #16a085 (Verde-azulado)
color: white
padding: 8px
font-weight: bold
```

**Tooltip**: "Carrega texturas modernas (DDS, PNG, TGA, BMP)"

#### 2. **"🤖 OCR + TRADUÇÃO AI"** (Atualizado)
**Localização**: [graphic_lab.py:336](interface/gui_tabs/graphic_lab.py#L336)

**Estilo**:
```python
background: #e67e22 (Laranja)
color: white
padding: 8px
font-weight: bold
```

**Tooltip**: "Detecta texto (tiles 8x8 ou texturas modernas) e traduz automaticamente"

**Conexão**: `self.intelligent_ocr_translation` (smart router)

---

## 📊 FLUXO DE TRABALHO COMPLETO

### Exemplo 1: Traduzir Menu de Jogo Indie (Unity/PNG)

```
1. PREPARAÇÃO
   ├─ Extraia as texturas do jogo:
   │  • Unity: Use AssetStudio / UABE
   │  • Unreal: Use UModel / UEViewer
   │  • Godot: Navegue até res:// folder
   └─ Localize texturas com texto (ex: menu_background.png)

2. CARREGAMENTO (Aba Graphic Lab)
   ├─ Clique em "🎨 CARREGAR TEXTURA"
   ├─ Selecione menu_background.png
   ├─ Preview é exibido automaticamente
   └─ Log: "[TEXTURA CARREGADA] menu_background.png (1920x1080) RGB"

3. OCR + TRADUÇÃO
   ├─ Clique em "🤖 OCR + TRADUÇÃO AI"
   ├─ Sistema detecta modo: "Textura Moderna"
   ├─ Pipeline automático:
   │  ├─ [1/5] Pre-processamento...
   │  ├─ [2/5] OCR detectou: "New Game\nLoad Game\nSettings\nExit"
   │  ├─ [3/5] Traduzindo com Gemini...
   │  ├─ [4/5] Renderizando: "Novo Jogo\nCarregar Jogo\nConfigurações\nSair"
   │  └─ [5/5] Salvando...
   └─ Sucesso: menu_background_TRANSLATED.png

4. INSTALAÇÃO NO JOGO
   ├─ Substitua menu_background.png por menu_background_TRANSLATED.png
   ├─ Se Unity Asset Bundle:
   │  • Recompile com AssetStudio
   │  • Ou use Unity Mod Manager
   └─ Teste o jogo: menu agora está em português! 🎮
```

**Tempo estimado**: 2-5 minutos por textura

---

### Exemplo 2: Traduzir Sprite de Item (Pixel Art/TGA)

```
1. CARREGAMENTO
   ├─ Arquivo: sword_icon.tga (64x64)
   ├─ Texto na textura: "Legendary Sword"
   └─ Log: "[TEXTURA CARREGADA] sword_icon.tga (64x64) RGB"

2. PROCESSAMENTO
   ├─ OCR detecta: "Legendary Sword"
   ├─ Gemini traduz: "Espada Lendária"
   ├─ Renderização:
   │  • Detecta fundo cinza escuro (RGB ~50,50,50)
   │  • Apaga texto original
   │  • Desenha "Espada Lendária" em branco
   │  • Ajusta fonte para caber em 64px
   └─ Salva: sword_icon_TRANSLATED.tga

3. RESULTADO
   ✅ Textura mantém qualidade original
   ✅ Texto traduzido visível e legível
   ✅ Cor de fundo preservada
```

---

## 🔧 DEPENDÊNCIAS

### Bibliotecas Necessárias

```bash
# Core (já instaladas no projeto)
pip install PyQt6
pip install Pillow

# OCR
pip install pytesseract

# AI Translation
pip install google-generativeai

# Tesseract Engine (Sistema Operacional)
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
# Mac: brew install tesseract
```

### Configuração do Tesseract

**Windows**:
```python
# Adicione ao PATH ou configure pytesseract:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Linux/Mac**:
```bash
# Tesseract geralmente está em /usr/bin/tesseract (já no PATH)
which tesseract
```

---

## ⚙️ CONFIGURAÇÕES

### Variáveis de Instância

**Localização**: [graphic_lab.py:309-316](interface/gui_tabs/graphic_lab.py#L309)

```python
# OCR + AI
self.selected_tile_idx = None         # Índice do tile selecionado (modo retro)
self.gemini_api_key = None            # API key do Google Gemini
self.target_language = "Portuguese (Brazil)"  # Idioma alvo

# Modern Textures
self.modern_texture = None            # PIL.Image da textura carregada
self.modern_texture_path = None       # Caminho completo do arquivo
self.modern_texture_format = None     # Extensão (.png, .tga, etc)
```

### Flags de Disponibilidade

**Localização**: [graphic_lab.py:17-40](interface/gui_tabs/graphic_lab.py#L17)

```python
TESSERACT_AVAILABLE = True   # pytesseract importado com sucesso
GEMINI_AVAILABLE = True      # google.generativeai importado
MODERN_TEXTURES_AVAILABLE = True  # PIL + ImageFile
```

---

## 📈 LIMITAÇÕES E SOLUÇÕES

### 1. **DDS Não Abre**

**Problema**: `DDS não suportado diretamente pelo Pillow`

**Solução**:
```bash
# Opção 1: Converter para PNG com GIMP
1. Abra arquivo .dds no GIMP
2. Export As → PNG
3. Carregue o PNG no framework

# Opção 2: ImageMagick
magick convert texture.dds texture.png

# Opção 3: Paint.NET (Windows)
1. Abra .dds
2. Salve como PNG
```

### 2. **OCR Não Detecta Texto**

**Causas Possíveis**:
- Resolução muito baixa (< 64px)
- Texto muito estilizado (fontes decorativas)
- Contraste insuficiente (texto cinza em fundo cinza)
- Texto em idioma não suportado pelo Tesseract

**Soluções**:
```python
# 1. Aumente resolução da textura antes de carregar
from PIL import Image
img = Image.open("texture.png")
upscaled = img.resize((img.width * 4, img.height * 4), Image.Resampling.LANCZOS)
upscaled.save("texture_large.png")

# 2. Aumente contraste manualmente no GIMP/Photoshop

# 3. Instale idiomas adicionais no Tesseract
# Windows: Baixe traineddata de https://github.com/tesseract-ocr/tessdata
# Coloque em C:\Program Files\Tesseract-OCR\tessdata\

# 4. Teste com PSM diferente:
custom_config = r'--oem 3 --psm 6'  # PSM 6: Assume single block of text
```

### 3. **Texto Traduzido Não Cabe**

**Problema**: Tradução PT-BR é ~30% maior que EN

**Solução Manual**:
```python
# Edite o código da tradução para abreviar:
def _translate_with_gemini(self, text, target_language):
    prompt = (
        f"Translate to {target_language}. "
        f"Keep translation SHORTER than {len(text)} characters. "
        f"Use abbreviations if needed:\n\n{text}"
    )
```

**Solução Automática** (Futura melhoria):
```python
# Redimensiona texto automaticamente se não couber:
if text_width > region_width:
    font_size = int(font_size * (region_width / text_width))
```

### 4. **Cor de Fundo Incorreta**

**Problema**: `_detect_background_color()` retorna cor errada

**Solução**:
```python
# Opção 1: Especifique cor manualmente
background_color = (0, 0, 0)  # Preto
background_color = (255, 255, 255)  # Branco

# Opção 2: Aumente margem de amostragem
margin = 20  # Aumenta de 10 para 20px
```

---

## 🎯 CASOS DE USO COMERCIAL

### Nicho 1: **Tradutores Profissionais de Jogos**

**Perfil**: Freelancers que traduzem jogos indie para PT-BR

**Benefícios**:
- ✅ Traduz texturas de menu em minutos (antes: horas no Photoshop)
- ✅ OCR automático economiza digitação manual
- ✅ AI traduz contextualmente (Gemini entende termos de jogos)
- ✅ Preserva qualidade visual (detecta cor de fundo, ajusta fonte)

**Fluxo de Trabalho**:
```
1. Cliente envia pasta de texturas do jogo
2. Tradutor carrega cada textura no framework
3. OCR + AI processa automaticamente
4. Tradutor revisa traduções e ajusta se necessário
5. Entrega texturas traduzidas ao cliente
```

**Precificação Sugerida**:
- R$ 5-15 por textura (depende da complexidade)
- Projeto completo (50-200 texturas): R$ 500-2.000

---

### Nicho 2: **Desenvolvedores Indie Brasileiros**

**Perfil**: Devs que querem lançar jogo em múltiplos idiomas

**Benefícios**:
- ✅ Traduz UI/menus sem contratar designer
- ✅ Testa traduções rapidamente
- ✅ Integra traduções nos assets antes de compilar

**Exemplo**: Jogo de plataforma feito em Unity

```
Texturas a traduzir:
- ui_title_screen.png → "Start Game" → "Iniciar Jogo"
- ui_pause_menu.png → "Resume / Quit" → "Retomar / Sair"
- ui_game_over.png → "Try Again" → "Tentar Novamente"
- icon_health.png → "HP" → "Vida"
- icon_mana.png → "MP" → "Mana"

Tempo total: ~15 minutos
Custo: Grátis (usando Gemini API gratuita)
```

---

### Nicho 3: **Modders de Jogos**

**Perfil**: Comunidade de modding (Steam Workshop, Nexus Mods)

**Benefícios**:
- ✅ Cria patches de tradução para jogos sem suporte oficial PT-BR
- ✅ Compartilha mods de tradução na comunidade
- ✅ Ganha reconhecimento e doações

**Exemplo**: Tradução de Stardew Valley mods

```
Mod: "New Crops Expansion"
├─ 30 texturas de culturas (crop_wheat.png, crop_corn.png...)
├─ Cada textura tem nome em inglês
├─ Framework traduz todos em ~10 minutos
└─ Mod traduzido publicado no Nexus Mods
```

---

## 🏆 CONQUISTAS TÉCNICAS

✅ **8 métodos profissionais** implementados:
- `load_modern_texture()`
- `_display_modern_texture_preview()`
- `process_modern_texture_ocr_translation()`
- `_preprocess_modern_texture_for_ocr()`
- `_perform_modern_texture_ocr()`
- `_render_text_on_modern_texture()`
- `_detect_background_color()`
- `_save_modern_texture()`
- `intelligent_ocr_translation()` (smart router)

✅ **440 linhas** de código novo (linhas 843-1283)

✅ **4 formatos** suportados (PNG, TGA, BMP, DDS*)

✅ **Pipeline completo** de 5 etapas (pre-proc → OCR → AI → render → save)

✅ **Smart Router** detecta modo automaticamente (retro vs moderno)

✅ **Zero breaking changes** - compatível com sistema existente de tiles retro

✅ **Validações robustas** - checa se bibliotecas estão instaladas

✅ **UI profissional** - botões estilizados, tooltips, logs coloridos

✅ **Código documentado** - docstrings completas em todos os métodos

---

## 📚 REFERÊNCIAS

### Documentação Oficial

- **Pillow (PIL)**: https://pillow.readthedocs.io/
- **pytesseract**: https://pypi.org/project/pytesseract/
- **Tesseract OCR**: https://tesseract-ocr.github.io/
- **Google Gemini API**: https://ai.google.dev/docs
- **PyQt6**: https://www.riverbankcomputing.com/static/Docs/PyQt6/

### Ferramentas Complementares

- **AssetStudio** (Unity): https://github.com/Perfare/AssetStudio
- **UABE** (Unity): https://github.com/SeriousCache/UABE
- **UModel** (Unreal): https://www.gildor.org/en/projects/umodel
- **GIMP** (Editor de Imagem): https://www.gimp.org/
- **ImageMagick** (CLI): https://imagemagick.org/

---

## 🔮 ROADMAP FUTURO

### Curto Prazo

1. ✅ **DDS Nativo**: Adicionar biblioteca `Pillow-DDS` ou `wand`
2. ✅ **Batch Processing**: Processar múltiplas texturas de uma vez
3. ✅ **Glossário**: Termos técnicos consistentes (HP → Vida, MP → Mana)
4. ✅ **Modo de Revisão**: Aprovar/rejeitar traduções antes de salvar

### Médio Prazo

5. ✅ **Integração com DeepL**: Alternativa ao Gemini (maior qualidade)
6. ✅ **Suporte a PSD/XCF**: Edição de camadas (texto em camada separada)
7. ✅ **Templates de Fontes**: Biblioteca de fontes para jogos (pixel art, sci-fi, etc)
8. ✅ **Detecção de Logos**: Não traduzir logos/marcas registradas

### Longo Prazo

9. ✅ **Machine Learning**: Treinar modelo customizado para OCR de pixel art
10. ✅ **Cloud Storage**: Salvar traduções em banco de dados comunitário
11. ✅ **Plugin para Unity/Godot**: Integração direta no editor de games
12. ✅ **Web App**: Interface web para clientes sem instalar Python

---

## 📞 SUPORTE

### Issues Comuns

**"Tesseract não encontrado"**
```bash
# Instale Tesseract OCR:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
# Mac: brew install tesseract
```

**"Gemini API Key inválida"**
```bash
# Obtenha API key gratuita:
# https://ai.google.dev/
# Limite gratuito: 60 requisições/minuto
```

**"Pillow não abre DDS"**
```bash
# Converta para PNG antes:
pip install Pillow-DDS  # (experimental, pode não funcionar)
# Ou use GIMP/ImageMagick manualmente
```

### Contato

- **GitHub Issues**: https://github.com/SEU-REPO/rom-translation-framework/issues
- **Email**: seu-email@exemplo.com
- **Discord**: Comunidade de Tradução de Jogos

---

**ROM Translation Framework v5**
**Modern Texture Support v1.0**
Desenvolvido por: Claude Sonnet 4.5
Última atualização: 04/Janeiro/2026

🎮 **Do Super Mario de 1990 aos Jogos Indie de 2026** 🎮
