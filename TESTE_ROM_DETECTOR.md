# 🧪 GUIA DE TESTE - ROM DETECTOR

## 📋 FASE 1: PREPARAÇÃO (5 minutos)

### 1. Edite o arquivo de teste:
Abra: `test_rom_detector.py`

Encontre a seção (linha ~20):
```python
test_roms = [
    # SUBSTITUA pelos caminhos REAIS das suas ROMs:
    (r"C:\caminho\para\Super Mario World.smc", "SNES"),
    (r"C:\caminho\para\Final Fantasy VII.bin", "PS1"),
    # ... etc
]
```

### 2. Adicione os caminhos das suas 10 ROMs:
```python
test_roms = [
    (r"C:\Roms\SNES\Super Mario World.smc", "SNES"),
    (r"C:\Roms\PS1\Final Fantasy VII.bin", "PS1"),
    (r"C:\Roms\N64\Zelda.n64", "N64"),
    (r"C:\Roms\Genesis\Sonic.gen", "GENESIS"),
    (r"C:\Roms\GBA\Metroid.gba", "GBA"),
    (r"C:\Roms\Wii\Mario Kart.iso", "WII"),
    (r"C:\Roms\PS2\God of War.iso", "PS2"),
    (r"C:\Roms\Xbox\Halo.xbe", "XBOX"),
    (r"C:\Roms\GB\Pokemon Red.gb", "GB"),
    (r"C:\Roms\NES\Castlevania.nes", "NES"),
]
```

## 🚀 FASE 2: EXECUTAR TESTES

### Opção 1: Teste Automático (RECOMENDADO)
```bash
cd "C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework"
python test_rom_detector.py
# Escolha opção 1
```

### Opção 2: Teste Interativo
```bash
python test_rom_detector.py
# Escolha opção 2
# Cole o caminho de cada ROM quando solicitado
```

## 📊 FASE 3: ANALISAR RESULTADOS

O script mostrará:
```
✅ CORRETO
  Arquivo: Super Mario World.smc
  Esperado: SNES
  Detectado: SNES (confiança: 100.0%)
  Categoria: ROM
```

Ou:
```
❌ INCORRETO
  Arquivo: game.iso
  Esperado: WII
  Detectado: PS2 (confiança: 70.0%)
  Categoria: ROM
```

### Relatório Final:
```
📊 RELATÓRIO FINAL
==============================
Total de ROMs testadas: 10
  ✅ Corretos: 8
  ❌ Incorretos: 2
  🔍 Não encontrados: 0

📈 PRECISÃO: 80.0%

⚠️ BOM, mas precisa melhorias.
```

## 📝 FASE 4: REPORTAR RESULTADOS

### Me envie:

1. **Precisão total** (ex: 80%)
2. **Quais arquivos ERRARAM** (nome + tipo esperado vs detectado)
3. **Confiança** de cada detecção
4. **Arquivo de relatório** (`rom_detector_report.txt`)

### Exemplo de reporte:
```
PRECISÃO: 70%

ERROS:
- Mario Kart.iso: esperado WII, detectou PS2 (confiança 70%)
- God of War.iso: esperado PS2, detectou PS1 (confiança 60%)
- Halo.xbe: esperado XBOX, não encontrou arquivo

ACERTOS:
- Super Mario World.smc: SNES (100%)
- Zelda.n64: N64 (100%)
- Sonic.gen: GENESIS (100%)
- etc.
```

## 🔧 FASE 5: ITERAÇÃO

Baseado nos erros, eu vou:
1. Ajustar os algoritmos de detecção
2. Melhorar a análise de conteúdo
3. Corrigir falsos positivos/negativos
4. Re-testar até atingir 90%+ de precisão

---

## ⚡ ATALHO RÁPIDO:

Se você já tem as ROMs em uma pasta, pode usar o modo interativo:

```bash
python test_rom_detector.py
# Escolha 2 (interativo)
# Cole o caminho: C:\Roms\SNES\Super Mario World.smc
# Veja o resultado
# Repita para cada ROM
```

---

## 📞 SUPORTE:

Se tiver problemas:
1. Verifique se os caminhos estão corretos
2. Use `r""` antes do caminho (raw string)
3. Remova espaços extras
4. Verifique se o arquivo existe

Pronto para testar! 🚀
