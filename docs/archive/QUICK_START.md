# ⚡ QUICK START - NOVO BACKEND AUTOMÁTICO

## 🎯 TESTAR O PIPELINE AGORA

### **Teste Standalone (sem GUI)**

```bash
# 1. Entre no diretório do projeto
cd "c:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework"

# 2. Execute análise completa em Super Mario World
python -m core.universal_pipeline "ROMs/Super Nintedo/Super Mario World.smc"

# Aguarde ~30-60 segundos

# 3. Verifique os resultados em:
# Super Mario World_output/
#   ├── rom_analysis.json
#   ├── compression_report.json
#   ├── text_candidates.json
#   ├── inferred_charsets/
#   │   ├── charset_candidate_1_frequency_based.json
#   │   ├── charset_candidate_2_position_based.json
#   │   └── charset_candidate_3_hybrid.json
#   ├── pointer_tables.json
#   └── extracted_texts_universal.json  ← ESTE É O PRINCIPAL
```

---

## 📊 ENTENDENDO OS RESULTADOS

### **extracted_texts_universal.json**

Abra este arquivo e você verá:

```json
{
  "rom_info": {
    "filename": "Super Mario World.smc",
    "platform": "SNES",
    "size": 524288
  },
  "analysis_summary": {
    "text_candidates_found": 142,
    "charset_tables_generated": 3,
    "pointer_tables_found": 3,
    "best_charset": "hybrid"
  },
  "extracted_texts": [
    {
      "id": 1,
      "offset": "0x81c0",
      "decoded_text": "SUPER MARIOWORLD",
      "score": 0.95,
      "pointers": [...]
    },
    ...
  ]
}
```

**O que avaliar**:
- ✅ `text_candidates_found` > 50: Bom
- ✅ `score` > 0.7: Texto de alta qualidade
- ✅ `decoded_text` legível: Charset inferido funciona
- ❌ Muitos `[XX]` no decoded_text: Charset não ideal

---

## 🧪 TESTE COMPLETO (EXTRAÇÃO + TRADUÇÃO + REINSERÇÃO)

### **Script de Teste Automático**

Crie arquivo `test_full_pipeline.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste completo do pipeline: Extração → Tradução → Reinserção
"""

import json
import sys
from pathlib import Path

# Adiciona diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.universal_pipeline import extract_rom_universal
from core.safe_reinserter import SafeReinserter
from interface.gemini_api import translate_batch

def test_full_pipeline(rom_path: str, api_key: str):
    """
    Teste completo: Extração → Tradução → Reinserção

    Args:
        rom_path: Caminho da ROM
        api_key: Chave da API Gemini
    """
    print("="*70)
    print("TESTE COMPLETO DO PIPELINE")
    print("="*70)

    # ETAPA 1: Extração
    print("\n[1/3] EXTRAÇÃO AUTOMÁTICA...")
    results = extract_rom_universal(rom_path)

    extraction_json = Path(rom_path).parent / f"{Path(rom_path).stem}_output" / "extracted_texts_universal.json"

    # Valida extração
    num_texts = len(results['extracted_texts'])
    print(f"✅ Extraídos: {num_texts} textos")

    if num_texts == 0:
        print("❌ FALHOU: Nenhum texto encontrado!")
        return False

    # ETAPA 2: Tradução (apenas primeiros 10 para teste)
    print("\n[2/3] TRADUÇÃO VIA GEMINI (teste com 10 textos)...")

    test_texts = []
    for entry in results['extracted_texts'][:10]:
        if entry['score'] >= 0.5 and not entry.get('is_compressed', False):
            test_texts.append(entry['decoded_text'])

    if not test_texts:
        print("⚠️  Nenhum texto válido para traduzir (scores baixos)")
        return False

    # Traduz
    translations, success, error = translate_batch(
        test_texts,
        api_key,
        "Portuguese (Brazil)",
        120.0
    )

    if not success:
        print(f"❌ ERRO na tradução: {error}")
        return False

    print(f"✅ Traduzidos: {len(translations)} textos")

    # Salva traduções
    translation_dict = {i+1: translations[i].strip() for i in range(len(translations))}

    translation_json = Path(rom_path).parent / f"{Path(rom_path).stem}_output" / "translations_test.json"
    with open(translation_json, 'w', encoding='utf-8') as f:
        json.dump(translation_dict, f, ensure_ascii=False, indent=2)

    # ETAPA 3: Reinserção
    print("\n[3/3] REINSERÇÃO SEGURA...")

    reinserter = SafeReinserter(rom_path, str(extraction_json))

    output_rom = str(Path(rom_path).with_stem(f"{Path(rom_path).stem}_test_translated"))

    success, message = reinserter.reinsert_translations(
        translations=translation_dict,
        output_path=output_rom,
        create_backup=True
    )

    if success:
        print(f"\n{'='*70}")
        print("✅ TESTE COMPLETO BEM-SUCEDIDO!")
        print(f"{'='*70}")
        print(f"ROM traduzida: {output_rom}")
        print(f"Backup: {rom_path}.backup")
        return True
    else:
        print(f"\n{'='*70}")
        print("❌ TESTE FALHOU NA REINSERÇÃO")
        print(f"{'='*70}")
        print(message)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_full_pipeline.py <rom_file> <gemini_api_key>")
        print("\nExample:")
        print('  python test_full_pipeline.py "ROMs/Super Nintedo/Super Mario World.smc" AIza...')
        sys.exit(1)

    rom = sys.argv[1]
    key = sys.argv[2]

    result = test_full_pipeline(rom, key)

    sys.exit(0 if result else 1)
```

**Execute**:

```bash
python test_full_pipeline.py "ROMs/Super Nintedo/Super Mario World.smc" "SUA_API_KEY_GEMINI"
```

---

## 🔍 VALIDAÇÃO DOS RESULTADOS

### **1. Verificar Extração**

```bash
# Ver resumo
python -c "import json; d=json.load(open('Super Mario World_output/extracted_texts_universal.json')); print(f'Textos: {len(d[\"extracted_texts\"])}, Charset: {d[\"analysis_summary\"][\"best_charset\"]}')"
```

### **2. Verificar Charset Inferido**

```bash
# Ver melhor charset
cat "Super Mario World_output/inferred_charsets/charset_candidate_3_hybrid.json"
```

Procure por:
- `"confidence"`: Deve ser > 0.6
- `"total_mappings"`: Deve ter > 30 caracteres
- `"byte_to_char"`: Verifique se letras comuns estão mapeadas

### **3. Testar ROM Traduzida**

```bash
# Abra no emulador
snes9x "Super Mario World_test_translated.smc"

# Ou use ZSNES, BSNES, etc
```

**O que verificar**:
- ✅ ROM inicia normalmente
- ✅ Não há caracteres estranhos (□, �, ▯)
- ✅ Textos estão em português
- ❌ Se crashar: problema na reinserção

---

## 🐛 TROUBLESHOOTING

### **Problema**: `ModuleNotFoundError: No module named 'core'`

**Solução**:
```bash
# Execute a partir da raiz do projeto
cd "c:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework"
python -m core.universal_pipeline "ROMs/Super Nintedo/Super Mario World.smc"
```

### **Problema**: Extração retorna 0 textos

**Causas possíveis**:
1. ROM comprimida (verifique `compression_report.json`)
2. Encoding muito custom (charset inference falhou)
3. ROM corrompida

**Solução**:
```bash
# Teste com ROM conhecida (Super Mario World)
# Se ainda falhar, reporte com logs
```

### **Problema**: Charset com baixa confiança (< 0.5)

**Causas**:
- Jogo usa tabela muito customizada
- Texto misturado com código

**Solução**:
- Use charset com maior confiança disponível
- Ou crie tabela manual baseada em `charset_candidate_X.json`

### **Problema**: Reinserção falha com "texto muito longo"

**Solução**:
```python
# Edite translations_test.json manualmente
# Encurte textos problemáticos:
{
  "5": "TEXTO MUITO LONGO AQUI" → "TEXTO CURTO"
}
```

---

## 📈 MÉTRICAS DE SUCESSO

### **Extração Boa**

```
✅ Textos encontrados: > 50
✅ Score médio: > 0.6
✅ Charset confidence: > 0.65
✅ Ponteiros detectados: > 10
```

### **Extração Razoável**

```
⚠️  Textos encontrados: 20-50
⚠️  Score médio: 0.4-0.6
⚠️  Charset confidence: 0.5-0.65
⚠️  Ponteiros detectados: 5-10
```

### **Extração Ruim** (precisa ajustes)

```
❌ Textos encontrados: < 20
❌ Score médio: < 0.4
❌ Charset confidence: < 0.5
❌ Ponteiros detectados: < 5
```

---

## 🎓 PRÓXIMOS PASSOS APÓS TESTE

1. **Se teste passou**:
   - Integre com GUI (veja [INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md))
   - Teste com outras ROMs (Lufia 2, Zelda)
   - Documente casos específicos

2. **Se teste falhou parcialmente**:
   - Revise charset inferido
   - Ajuste threshold de score (line 51 em text_scanner.py)
   - Adicione filtros customizados

3. **Se teste falhou completamente**:
   - Execute módulos individuais para diagnosticar:
     ```bash
     python -m core.rom_analyzer game.smc
     python -m core.text_scanner game.smc
     python -m core.charset_inference game.smc
     ```
   - Verifique logs em `translator_debug.log`
   - Reporte issue com ROM específica

---

## 📞 SUPORTE RÁPIDO

**Logs importantes**:
- `translator_debug.log`: Erros gerais
- `*_output/rom_analysis.json`: Info da ROM
- `*_output/compression_report.json`: Compressão detectada

**Comandos úteis**:
```bash
# Ver estrutura de saída
tree Super\ Mario\ World_output/

# Ver primeiros textos extraídos
jq '.extracted_texts[:5]' Super\ Mario\ World_output/extracted_texts_universal.json

# Ver melhor charset
jq '.name, .confidence' Super\ Mario\ World_output/inferred_charsets/charset_candidate_3_hybrid.json
```

---

**Pronto para testar!** 🚀

Execute:
```bash
python -m core.universal_pipeline "ROMs/Super Nintedo/Super Mario World.smc"
```

E veja a mágica acontecer! ✨
