# 🔗 GUIA DE INTEGRAÇÃO - NOVO BACKEND COM GUI EXISTENTE

## 📋 VISÃO GERAL

Este documento explica como integrar os novos módulos de análise automática com a interface gráfica existente (`interface_tradutor_final.py`).

---

## 🏗️ ARQUITETURA DOS NOVOS MÓDULOS

```
core/
├── rom_analyzer.py          → Análise estrutural da ROM
├── text_scanner.py          → Detecção heurística de texto
├── charset_inference.py     → Inferência de tabela de caracteres
├── pointer_scanner.py       → Detecção de ponteiros
├── compression_detector.py  → Identificação de compressão
├── universal_pipeline.py    → Orquestrador completo
└── safe_reinserter.py       → Reinserção segura
```

---

## 🔄 PIPELINE AUTOMÁTICO

### **Fluxo Completo**

```
ROM Original
    ↓
[1] ROMAnalyzer          → Detecta plataforma, mapeamento, entropia
    ↓
[2] CompressionDetector  → Identifica regiões comprimidas
    ↓
[3] TextScanner          → Varre e detecta strings de texto
    ↓
[4] CharsetInference     → Descobre tabela de caracteres
    ↓
[5] PointerScanner       → Mapeia ponteiros para textos
    ↓
[6] Export Universal     → Gera extracted_texts_universal.json
    ↓
[TRADUÇÃO via Gemini API]
    ↓
[7] SafeReinserter       → Reinsere usando charset inferido
    ↓
ROM Traduzida
```

---

## 🛠️ INTEGRAÇÃO COM A GUI

### **Opção 1: Botão "Análise Automática" (RECOMENDADO)**

Adicionar novo botão na aba de Extração:

```python
# Em interface_tradutor_final.py, classe ROMTranslatorGUI

def _create_extraction_tab(self):
    # ... código existente ...

    # NOVO: Botão de análise automática
    self.btn_auto_analyze = QPushButton("🔬 ANÁLISE AUTOMÁTICA")
    self.btn_auto_analyze.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            padding: 12px;
            border-radius: 5px;
        }
        QPushButton:hover { background-color: #45a049; }
    """)
    self.btn_auto_analyze.clicked.connect(self.on_auto_analyze_clicked)
    extraction_layout.addWidget(self.btn_auto_analyze)

def on_auto_analyze_clicked(self):
    """Executa pipeline automático completo."""
    if not self.rom_path:
        QMessageBox.warning(self, "Erro", "Selecione uma ROM primeiro!")
        return

    # Importa pipeline
    from core.universal_pipeline import UniversalExtractionPipeline

    # Desabilita botão durante processamento
    self.btn_auto_analyze.setEnabled(False)
    self.btn_auto_analyze.setText("⏳ Analisando...")

    try:
        # Executa pipeline em thread
        output_dir = Path(self.rom_path).parent / f"{Path(self.rom_path).stem}_analysis"

        # TODO: Mover para QThread para não travar UI
        pipeline = UniversalExtractionPipeline(self.rom_path, str(output_dir))
        results = pipeline.run_full_analysis()

        # Atualiza log
        self.log_area.append(f"\n✅ Análise automática concluída!")
        self.log_area.append(f"📊 Textos encontrados: {results['analysis_summary']['text_candidates_found']}")
        self.log_area.append(f"📂 Resultados salvos em: {output_dir}")

        # Armazena caminho do JSON para próximas etapas
        self.extracted_json_path = str(output_dir / "extracted_texts_universal.json")

        # Habilita próximos passos
        self.btn_translate.setEnabled(True)

    except Exception as e:
        QMessageBox.critical(self, "Erro", f"Erro na análise automática:\n{str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        self.btn_auto_analyze.setEnabled(True)
        self.btn_auto_analyze.setText("🔬 ANÁLISE AUTOMÁTICA")
```

---

### **Opção 2: Substituir Extração Existente**

Modificar método que chama `generic_snes_extractor.py`:

```python
def _extract_with_new_pipeline(self):
    """Substitui extração antiga por pipeline novo."""
    from core.universal_pipeline import extract_rom_universal

    try:
        # Executa extração automática
        results = extract_rom_universal(
            rom_path=self.rom_path,
            output_dir=None  # Auto-gera diretório
        )

        # Carrega textos extraídos
        self.extracted_texts = results['extracted_texts']

        # Exibe no log
        for text in self.extracted_texts[:10]:  # Primeiros 10
            self.log_area.append(
                f"[{text['id']}] 0x{text['offset']}: {text['decoded_text'][:50]}"
            )

        return True

    except Exception as e:
        self.log_area.append(f"❌ Erro: {str(e)}")
        return False
```

---

### **Opção 3: Integração com Gemini (Tradução)**

Modificar método de tradução para usar formato universal:

```python
def _translate_with_gemini_new_format(self):
    """Traduz usando formato universal do novo pipeline."""
    import json
    from interface.gemini_api import translate_batch

    # Carrega JSON de extração
    with open(self.extracted_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts_to_translate = []
    for entry in data['extracted_texts']:
        # Filtra textos de baixa qualidade
        if entry['score'] < 0.5:
            continue

        # Pula textos em regiões comprimidas (não suportado ainda)
        if entry.get('is_compressed', False):
            continue

        texts_to_translate.append(entry['decoded_text'])

    # Traduz em lotes
    all_translations = []
    batch_size = 15

    for i in range(0, len(texts_to_translate), batch_size):
        batch = texts_to_translate[i:i+batch_size]

        # Chama Gemini
        translations, success, error = translate_batch(
            batch,
            api_key=self.api_key,
            target_language="Portuguese (Brazil)",
            timeout=120.0
        )

        if success:
            all_translations.extend([t.strip() for t in translations])

            # Atualiza progresso
            progress = min(100, int((i + batch_size) / len(texts_to_translate) * 100))
            self.progress_bar.setValue(progress)
        else:
            self.log_area.append(f"⚠️ Erro no lote {i//batch_size + 1}: {error}")
            all_translations.extend(batch)  # Usa original em caso de erro

    # Salva traduções em formato para SafeReinserter
    translation_output = {}
    for i, translation in enumerate(all_translations, 1):
        translation_output[i] = translation

    translation_path = Path(self.extracted_json_path).parent / "translations.json"
    with open(translation_path, 'w', encoding='utf-8') as f:
        json.dump(translation_output, f, indent=2, ensure_ascii=False)

    self.log_area.append(f"✅ Traduções salvas: {translation_path}")
    self.translation_json_path = str(translation_path)
```

---

### **Opção 4: Reinserção Segura**

Substituir `ReinsertionWorker` por SafeReinserter:

```python
def _reinsert_with_safe_reinserter(self):
    """Usa SafeReinserter para reinserção segura."""
    from core.safe_reinserter import SafeReinserter

    try:
        # Cria reinsertor
        reinserter = SafeReinserter(
            rom_path=self.rom_path,
            extraction_data_path=self.extracted_json_path
        )

        # Carrega traduções
        with open(self.translation_json_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)

        # Converte IDs para int
        translations = {int(k): v for k, v in translations.items()}

        # Define saída
        output_path = str(Path(self.rom_path).with_stem(
            f"{Path(self.rom_path).stem}_translated"
        ))

        # Executa reinserção
        success, message = reinserter.reinsert_translations(
            translations=translations,
            output_path=output_path,
            create_backup=True
        )

        # Exibe resultado
        if success:
            self.log_area.append(f"✅ {message}")
            QMessageBox.information(self, "Sucesso", message)
        else:
            self.log_area.append(f"⚠️ {message}")
            QMessageBox.warning(self, "Atenção", message)

        return success

    except Exception as e:
        error_msg = f"Erro na reinserção: {str(e)}"
        self.log_area.append(f"❌ {error_msg}")
        QMessageBox.critical(self, "Erro", error_msg)
        return False
```

---

## 📝 EXEMPLO DE INTEGRAÇÃO COMPLETA

```python
# Adicionar ao __init__ da classe ROMTranslatorGUI

def __init__(self):
    super().__init__()

    # ... código existente ...

    # NOVO: Caminhos para arquivos do novo pipeline
    self.extracted_json_path = None
    self.translation_json_path = None
    self.use_new_pipeline = True  # Flag para ativar novo backend

# Modificar fluxo de extração

def on_extract_button_clicked(self):
    if self.use_new_pipeline:
        self.on_auto_analyze_clicked()  # Usa novo pipeline
    else:
        self._old_extraction_method()  # Mantém método antigo
```

---

## 🧪 TESTE DE INTEGRAÇÃO

### **Teste Básico**

```python
# test_integration.py

from core.universal_pipeline import extract_rom_universal
from core.safe_reinserter import reinsert_from_translation_file

# Passo 1: Extração
rom_path = "ROMs/Super Nintedo/Super Mario World.smc"
results = extract_rom_universal(rom_path)

# Passo 2: Simulação de tradução
translations = {
    entry['id']: f"TRADUZIDO: {entry['decoded_text']}"
    for entry in results['extracted_texts'][:10]  # Primeiros 10
}

import json
translation_path = "test_translations.json"
with open(translation_path, 'w', encoding='utf-8') as f:
    json.dump(translations, f, ensure_ascii=False, indent=2)

# Passo 3: Reinserção
extraction_json = "Super Mario World_output/extracted_texts_universal.json"
success = reinsert_from_translation_file(
    rom_path=rom_path,
    extraction_json=extraction_json,
    translation_json=translation_path,
    output_path="test_translated.smc"
)

print(f"✅ Teste {'PASSOU' if success else 'FALHOU'}")
```

---

## ⚠️ AVISOS IMPORTANTES

### **1. Threading**

**PROBLEMA**: Pipeline pode demorar 30-60 segundos, travando a UI.

**SOLUÇÃO**: Mover para QThread

```python
class AnalysisThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, rom_path, output_dir):
        super().__init__()
        self.rom_path = rom_path
        self.output_dir = output_dir

    def run(self):
        try:
            from core.universal_pipeline import UniversalExtractionPipeline
            pipeline = UniversalExtractionPipeline(self.rom_path, self.output_dir)
            results = pipeline.run_full_analysis()
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
```

### **2. Compatibilidade Retroativa**

**Manter funcionalidade antiga** enquanto testa nova:

```python
# Adicionar checkbox na GUI
self.chk_use_new_backend = QCheckBox("Usar novo backend (experimental)")
self.chk_use_new_backend.setChecked(False)
```

### **3. Validação de Resultados**

**Sempre validar** antes de sobresc rever ROM:

```python
if len(extracted_texts) == 0:
    QMessageBox.warning(self, "Aviso", "Nenhum texto encontrado!")
    return

if len(extracted_texts) < 10:
    result = QMessageBox.question(
        self, "Confirmar",
        f"Apenas {len(extracted_texts)} textos encontrados. Continuar?",
        QMessageBox.Yes | QMessageBox.No
    )
    if result == QMessageBox.No:
        return
```

---

## 📊 MÉTRICAS DE QUALIDADE

Para avaliar se o novo pipeline está funcionando:

```python
def evaluate_extraction_quality(results):
    """Calcula métricas de qualidade da extração."""
    texts = results['extracted_texts']

    metrics = {
        'total_texts': len(texts),
        'high_confidence': sum(1 for t in texts if t['score'] >= 0.7),
        'with_pointers': sum(1 for t in texts if t['pointers']),
        'avg_length': sum(t['length'] for t in texts) / len(texts) if texts else 0,
        'charset_confidence': results['analysis_summary'].get('best_charset_confidence', 0)
    }

    # Score geral (0-100)
    quality_score = (
        (metrics['high_confidence'] / metrics['total_texts'] * 40) +
        (metrics['with_pointers'] / metrics['total_texts'] * 30) +
        (min(metrics['total_texts'] / 100, 1.0) * 30)
    )

    return metrics, quality_score
```

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ Implementar botão "Análise Automática" na GUI
2. ✅ Mover processamento para QThread
3. ✅ Adicionar barra de progresso por etapa
4. ✅ Testar com 3 ROMs diferentes
5. ✅ Documentar erros comuns
6. ✅ Criar modo "debug" com logs detalhados

---

## 📞 SUPORTE

Se encontrar problemas na integração:

1. Verifique logs em `translator_debug.log`
2. Execute pipeline standalone primeiro: `python -m core.universal_pipeline game.smc`
3. Valide JSONs gerados manualmente
4. Reporte com traceback completo

---

**Última atualização**: 2025-01-10
**Versão do Backend**: 1.0
**Compatível com GUI**: interface_tradutor_final.py v5.3+
