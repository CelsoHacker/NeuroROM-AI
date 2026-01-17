# 🎮 MÓDULOS PC GAMES - PRÓXIMOS PASSOS

## ✅ JÁ CRIADOS

1. **[core/pc_game_scanner.py](../core/pc_game_scanner.py)** ✅
   - Varre diretório do jogo automaticamente
   - Detecta arquivos com texto (.txt, .json, .xml, .ini, .lua, etc)
   - Identifica pastas de localização (lang/, localization/, etc)
   - Sistema de prioridade (arquivos mais prováveis primeiro)
   - Exporta lista em JSON

2. **[core/file_format_detector.py](../core/file_format_detector.py)** ✅
   - Detecta formato automaticamente (JSON, XML, YAML, INI, CSV, etc)
   - Identifica delimitadores e estrutura
   - Encontra localizações de texto dentro do formato
   - Preserva metadados para reinserção

---

## 📋 PRÓXIMOS MÓDULOS (CRIAR)

### 3. **core/encoding_detector.py** (CRÍTICO)

```python
"""
Detecta e preserva encoding de arquivos de jogos.
- UTF-8, UTF-16, Windows-1252, Shift-JIS, etc
- Detecta BOM (Byte Order Mark)
- Valida encoding antes de processar
- Garante reinserção no mesmo encoding
"""
```

### 4. **core/pc_text_extractor.py** (PRINCIPAL)

```python
"""
Extrator universal para arquivos PC.
- Usa FileFormatDetector para entender estrutura
- Extrai texto preservando contexto (chave JSON, tag XML, etc)
- Gera formato universal:
  {
    "file": "data/strings.json",
    "format": "json",
    "encoding": "utf-8",
    "texts": [
      {
        "id": 1,
        "path": "menu.title",
        "original": "Main Menu",
        "context": {"file_line": 10}
      }
    ]
  }
"""
```

### 5. **core/pc_safe_reinserter.py** (CRÍTICO)

```python
"""
Reinsertor seguro para arquivos PC.
- Usa formato extraído para reconstruir
- Mantém estrutura original (indentação JSON, ordem XML)
- Valida sintaxe antes de salvar (JSON válido, XML well-formed)
- Preserva encoding original
- Cria backups automáticos
"""
```

### 6. **core/pc_pipeline.py** (ORQUESTRADOR)

```python
"""
Pipeline integrado para jogos PC.

Fluxo:
1. PCGameScanner → Encontra arquivos
2. FileFormatDetector → Detecta formatos
3. EncodingDetector → Valida encodings
4. PCTextExtractor → Extrai textos
5. [TRADUÇÃO via Gemini]
6. PCSafeReinserter → Reinsere traduções

Output: Jogo traduzido com estrutura preservada
"""
```

---

## 🧪 TESTE COM DARKNESS WITHIN (SEM HARDCODE)

### **Exemplo de uso**:

```python
from core.pc_pipeline import translate_pc_game

# Traduz jogo completo automaticamente
translate_pc_game(
    game_path="C:/Games/Darkness Within",
    output_path="C:/Games/Darkness Within - PT-BR",
    api_key="YOUR_GEMINI_KEY",
    target_language="Portuguese (Brazil)"
)
```

### **Validação**:
- ✅ NÃO deve ter código específico para Darkness Within
- ✅ Deve funcionar com qualquer jogo PC
- ✅ Deve preservar estrutura de todos os formatos
- ✅ Deve detectar automaticamente arquivos traduzíveis

---

## 📊 FORMATO UNIVERSAL DE EXTRAÇÃO (PC GAMES)

```json
{
  "game_info": {
    "name": "Detected from folder name",
    "path": "C:/Games/SomeGame",
    "total_files": 1247,
    "translatable_files": 45
  },
  "files": [
    {
      "file_path": "data/strings.json",
      "format": "json",
      "encoding": "utf-8",
      "priority": 80,
      "texts": [
        {
          "id": 1,
          "path": "menu.main.title",
          "original_text": "Main Menu",
          "context": {
            "file_line": 10,
            "json_path": "menu.main.title"
          }
        }
      ]
    },
    {
      "file_path": "config/game.ini",
      "format": "ini",
      "encoding": "windows-1252",
      "priority": 50,
      "texts": [
        {
          "id": 50,
          "path": "General.GameName",
          "original_text": "My Game",
          "context": {
            "section": "General",
            "key": "GameName"
          }
        }
      ]
    }
  ],
  "metadata": {
    "extraction_date": "2025-01-10T...",
    "total_texts": 1523,
    "ready_for_translation": true
  }
}
```

---

## 🔧 INTEGRAÇÃO COM GUI EXISTENTE

### **Adicionar aba "PC Games" em interface_tradutor_final.py**:

```python
def _create_pc_games_tab(self):
    """Nova aba para jogos PC."""
    pc_tab = QWidget()
    layout = QVBoxLayout()

    # Botão: Selecionar pasta do jogo
    btn_select_game = QPushButton("📁 Selecionar Pasta do Jogo")
    btn_select_game.clicked.connect(self.on_select_pc_game)
    layout.addWidget(btn_select_game)

    # Botão: Análise automática
    btn_auto_scan = QPushButton("🔍 ESCANEAR ARQUIVOS")
    btn_auto_scan.clicked.connect(self.on_scan_pc_game)
    layout.addWidget(btn_auto_scan)

    # Lista de arquivos encontrados
    self.pc_files_list = QTextEdit()
    self.pc_files_list.setReadOnly(True)
    layout.addWidget(self.pc_files_list)

    # Botão: Extrair textos
    btn_extract_pc = QPushButton("📤 EXTRAIR TEXTOS")
    btn_extract_pc.clicked.connect(self.on_extract_pc_texts)
    layout.addWidget(btn_extract_pc)

    # Botão: Traduzir
    btn_translate_pc = QPushButton("🌐 TRADUZIR")
    btn_translate_pc.clicked.connect(self.on_translate_pc_texts)
    layout.addWidget(btn_translate_pc)

    # Botão: Reinserir
    btn_reinsert_pc = QPushButton("💾 GERAR JOGO TRADUZIDO")
    btn_reinsert_pc.clicked.connect(self.on_reinsert_pc_texts)
    layout.addWidget(btn_reinsert_pc)

    pc_tab.setLayout(layout)
    self.tabs.addTab(pc_tab, "🎮 PC Games")
```

---

## ⚠️ REGRAS CRÍTICAS

### **NÃO fazer**:
- ❌ Hardcode de nomes de jogos
- ❌ Profiles específicos (ex: "darkness_within.json")
- ❌ Assumir estrutura fixa de pastas
- ❌ Quebrar compatibilidade com ROMs

### **SEMPRE fazer**:
- ✅ Detecção automática
- ✅ Heurísticas genéricas
- ✅ Validação antes de escrever
- ✅ Backups automáticos
- ✅ Preservação de estrutura original

---

## 📈 PRIORIDADE DE IMPLEMENTAÇÃO

1. **URGENTE**: `encoding_detector.py` (sem isso, pode corromper arquivos)
2. **CRÍTICO**: `pc_text_extractor.py` (núcleo da funcionalidade)
3. **CRÍTICO**: `pc_safe_reinserter.py` (reinserção segura)
4. **IMPORTANTE**: `pc_pipeline.py` (automatização)
5. **OPCIONAL**: Integração com GUI (pode ser CLI primeiro)

---

## 🧪 VALIDAÇÃO FINAL

```bash
# Teste completo standalone
python -m core.pc_pipeline "C:/Games/Darkness Within"

# Deve gerar:
# Darkness Within_output/
#   ├── game_files_scan.json
#   ├── extracted_texts_pc.json
#   ├── translations.json (após Gemini)
#   └── [arquivos traduzidos preservando estrutura]
```

---

**Status**: 2/6 módulos criados
**Próximo**: Criar `encoding_detector.py`
**Compatibilidade**: 100% com sistema de ROMs existente
