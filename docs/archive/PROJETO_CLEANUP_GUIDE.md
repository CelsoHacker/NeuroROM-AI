# 🧹 GUIA DE LIMPEZA - PROJETO_V5_OFICIAL

## 📋 ANÁLISE COMPLETA DA ESTRUTURA

### ✅ ARQUIVOS E PASTAS ESSENCIAIS (MANTER)

#### **📁 core/** - Sistema principal (MANTER TUDO)
```
✅ charset_inference.py          (450 linhas) - Inferência de charset ROMs
✅ compression_detector.py        (390 linhas) - Detecta compressão
✅ encoding_detector.py           (550 linhas) - Detecta encoding PC games
✅ file_format_detector.py        (480 linhas) - Detecta formatos PC
✅ pc_game_scanner.py             (430 linhas) - Scanner PC games
✅ pc_pipeline.py                 (380 linhas) - Pipeline PC completo
✅ pc_safe_reinserter.py          (720 linhas) - Reinserção PC
✅ pc_text_extractor.py           (680 linhas) - Extração PC
✅ pointer_scanner.py             (520 linhas) - Scanner de ponteiros ROM
✅ rom_analyzer.py                (420 linhas) - Análise de ROMs
✅ safe_reinserter.py             (410 linhas) - Reinserção ROM
✅ text_scanner.py                (380 linhas) - Scanner de texto ROM
✅ universal_pipeline.py          (280 linhas) - Pipeline ROM universal
✅ __init__.py                    - Módulo Python
```

**Arquivos DUPLICADOS/OBSOLETOS em core/ (DELETAR)**:
```
❌ gemini_translator.py          - Duplicado de interface/gemini_api.py
❌ parallel_translator.py         - Não usado (tradução é via gemini_api.py)
❌ translation_engine.py          - Duplicado de interface/gemini_api.py
❌ translator_engine.py           - Duplicado de interface/gemini_api.py
```

---

#### **📁 interface/** - GUI e APIs (REVISAR)

**MANTER**:
```
✅ interface_tradutor_final.py   (1729 linhas) - GUI PRINCIPAL
✅ gemini_api.py                 (197 linhas) - API Gemini FUNCIONAL
✅ __init__.py                   - Módulo Python
```

**ARQUIVOS OBSOLETOS (DELETAR)**:
```
❌ gui_translator.py             (1536 linhas) - GUI ANTIGA (substituída por interface_tradutor_final.py)
❌ pointer_scanner.py            (620 linhas) - DUPLICADO de core/pointer_scanner.py
❌ memory_mapper.py              (617 linhas) - Funcionalidade já em core/rom_analyzer.py
❌ generic_snes_extractor.py     (163 linhas) - OBSOLETO (substituído por core/universal_pipeline.py)
❌ integration_patch.py          (273 linhas) - Patch temporário, não mais necessário
❌ tempCodeRunnerFile.py         (1 linha) - Arquivo temporário do VSCode
```

**ARQUIVOS DE CONFIGURAÇÃO (REVISAR)**:
```
⚠️ config.json                   - Verificar se usado
⚠️ salvar_info_jogo.json         - Backup de configuração (pode deletar se não usado)
⚠️ translator_config.json        - Verificar se usado
```

---

#### **📁 docs/** - Documentação (CONSOLIDAR)

**DOCUMENTAÇÃO ATUAL E ÚTIL (MANTER)**:
```
✅ 00_START_HERE.md              - Guia inicial
✅ BACKEND_EVOLUTION_SUMMARY.md  - Histórico ROM system
✅ GUI_INTEGRATION_PC.md         - Integração PC (NOVO)
✅ INTEGRATION_GUIDE.md          - Integração ROM
✅ PC_GAMES_IMPLEMENTATION.md    - Sistema PC completo (NOVO)
✅ PC_GAMES_MODULES_TODO.md      - Especificação PC
✅ QUICK_REFERENCE.md            - Referência rápida
✅ TECHNICAL_ARCHITECTURE.md     - Arquitetura técnica
```

**DOCUMENTAÇÃO OBSOLETA/DUPLICADA (DELETAR)**:
```
❌ 7_DAY_ROADMAP.md              - Roadmap antigo (já implementado)
❌ BUG_FIX_DELIVERY.md           - Relatório de bugs corrigidos (arquivar)
❌ CHANGELOG.md                  - Log de mudanças desatualizado
❌ COMPLETE_GUIDE.txt            - Duplicado de outros docs
❌ GUIA_TESTES_LEGAL_SEGURO.md   - Testes legais (mover para /security/docs)
❌ LAUNCH_STRATEGY.md            - Estratégia de lançamento (arquivar)
❌ MANUAL_USO.md                 - Duplicado de QUICK_REFERENCE.md
❌ PROJECT_ANALYSIS_REPORT.md    - Relatório antigo (arquivar)
❌ README.txt                    - Duplicado de README.md
❌ RELATORIO_CORRECOES.md        - Relatório de correções (arquivar)
❌ requirements.txt              - Está em lugar errado (mover para raiz)
❌ SOLUCAO_LEGAL_E_SEGURA.md     - Duplicado de GUIA_TESTES
❌ TECHNICAL_MANUAL.txt          - Duplicado de TECHNICAL_ARCHITECTURE.md
```

---

#### **📁 tools/** - Ferramentas (MANTER)
```
✅ entropy_analyzer.py           - Análise de entropia
✅ relative_searcher.py          - Busca relativa
✅ text_cleaner.py               - Limpeza de texto
✅ text_extractor.py             - Extrator genérico
✅ __init__.py
```

---

#### **📁 security/** - Segurança (MANTER)
```
✅ license_guard.py              - Proteção de licença
✅ __init__.py
```

---

#### **📁 utils/** - Utilitários (REVISAR)
```
✅ system_diagnostics.py         - Diagnósticos do sistema
❌ license_guard.py              - DUPLICADO de security/license_guard.py (DELETAR)
❌ cuda_optimizer.py             - Não usado (não há código CUDA no projeto)
```

---

#### **📁 data/** - Dados (MANTER)
```
✅ mapa_ponteiros.json           - Mapa de ponteiros para ROMs
```

---

#### **📁 examples/** - Exemplos (MANTER)
```
✅ ps1_config.json               - Exemplo de config PS1
✅ snes_config.json              - Exemplo de config SNES
```

---

#### **📁 dummy_pc_game/** - Jogo de teste (LIMPAR)

**MANTER**:
```
✅ config/settings.ini
✅ localization/english.json
✅ localization/strings.xml
✅ scripts/quest_manager.lua
```

**DELETAR**:
```
❌ extracted_texts_pc.json       - Arquivo de teste (pode recriar)
❌ test_translations.json        - Arquivo de teste (pode recriar)
❌ translation_output/           - Pasta de saída de teste
❌ localization/*.backup_*       - Backups de teste
```

---

#### **📁 ROMs/** - ROMs de teste

**ATENÇÃO**: ROMs são propriedade protegida por direitos autorais!

**Opção 1 - Projeto Pessoal (MANTER para testes)**:
```
✅ Super Nintedo/*.smc           - ROMs de teste
✅ Playstation 1/*.bin
```

**Opção 2 - Projeto Público (DELETAR TUDO)**:
```
❌ DELETAR TODAS AS ROMs
❌ Adicionar ROMs/ ao .gitignore
❌ Documentar que usuário deve fornecer próprias ROMs
```

**DELETAR (arquivos temporários)**:
```
❌ Super Mario World_extracted_texts.txt
❌ Super Mario World_optimized.txt
❌ Super Mario World_translated.txt
```

---

#### **📁 Scripts principais/** - Scripts (VERIFICAR CONTEÚDO)

**Pasta vazia ou com scripts temporários**:
```
❓ Verificar conteúdo
❌ Se vazia ou com código duplicado, DELETAR pasta inteira
```

---

#### **📄 Arquivos Raiz**

**MANTER**:
```
✅ .gitignore                    - Configuração Git
✅ LICENSE                       - Licença do projeto
✅ QUICK_START.md                - Guia rápido
✅ test_encoding_detector.py     - Testes de encoding
✅ estrutura_projeto.txt         - Documentação de estrutura
```

**DELETAR**:
```
❌ MANUAL_USO.pdf                - 4MB! Duplicado de documentação .md (converter para .md se necessário)
```

---

#### **🗑️ Cache e Arquivos Temporários (DELETAR SEMPRE)**

```
❌ core/__pycache__/             - Cache Python
❌ interface/__pycache__/        - Cache Python
❌ tools/__pycache__/            - Cache Python
❌ utils/__pycache__/            - Cache Python
❌ security/__pycache__/         - Cache Python
❌ *.pyc                         - Bytecode Python
❌ *.backup_*                    - Backups de teste
❌ *_output/                     - Pastas de saída temporárias
```

---

## 📊 RESUMO DE LIMPEZA

### **Estatísticas Atuais**
- **Arquivos Python**: ~30 arquivos
- **Documentação**: ~20 arquivos .md/.txt
- **Cache**: ~15 arquivos .pyc
- **ROMs**: ~5 arquivos (problemático se público)
- **PDF**: 1 arquivo de 4MB (desnecessário)

### **Após Limpeza**
- ✅ **Arquivos Python essenciais**: 20 arquivos (~7.500 linhas úteis)
- ✅ **Documentação consolidada**: 8 arquivos principais
- ✅ **0 duplicatas**
- ✅ **0 cache**
- ✅ **0 ROMs** (se projeto público)

---

## 🚀 SCRIPT DE LIMPEZA AUTOMÁTICA

### **Windows (PowerShell)**

```powershell
# Execute na raiz do projeto (PROJETO_V5_OFICIAL)

# 1. Remove cache Python
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force

# 2. Remove backups de teste
Get-ChildItem -Recurse -Filter "*.backup_*" | Remove-Item -Force

# 3. Remove duplicatas em core/
Remove-Item "rom-translation-framework\core\gemini_translator.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\core\parallel_translator.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\core\translation_engine.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\core\translator_engine.py" -ErrorAction SilentlyContinue

# 4. Remove arquivos obsoletos em interface/
Remove-Item "rom-translation-framework\interface\gui_translator.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\interface\pointer_scanner.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\interface\memory_mapper.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\interface\generic_snes_extractor.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\interface\integration_patch.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\interface\tempCodeRunnerFile.py" -ErrorAction SilentlyContinue

# 5. Remove duplicata em utils/
Remove-Item "rom-translation-framework\utils\license_guard.py" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\utils\cuda_optimizer.py" -ErrorAction SilentlyContinue

# 6. Remove documentação obsoleta
Remove-Item "rom-translation-framework\docs\7_DAY_ROADMAP.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\BUG_FIX_DELIVERY.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\CHANGELOG.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\COMPLETE_GUIDE.txt" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\LAUNCH_STRATEGY.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\MANUAL_USO.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\PROJECT_ANALYSIS_REPORT.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\README.txt" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\RELATORIO_CORRECOES.md" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\docs\TECHNICAL_MANUAL.txt" -ErrorAction SilentlyContinue

# 7. Remove PDF grande
Remove-Item "rom-translation-framework\MANUAL_USO.pdf" -ErrorAction SilentlyContinue

# 8. Remove arquivos temporários de teste
Remove-Item "rom-translation-framework\dummy_pc_game\extracted_texts_pc.json" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\dummy_pc_game\test_translations.json" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\dummy_pc_game\translation_output" -Recurse -ErrorAction SilentlyContinue

# 9. Remove outputs de ROM teste
Remove-Item "rom-translation-framework\ROMs\Super Nintedo\*_extracted_texts.txt" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\ROMs\Super Nintedo\*_optimized.txt" -ErrorAction SilentlyContinue
Remove-Item "rom-translation-framework\ROMs\Super Nintedo\*_translated.txt" -ErrorAction SilentlyContinue

# 10. Remove "Scripts principais" se vazia
if ((Get-ChildItem "rom-translation-framework\Scripts principais" -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Remove-Item "rom-translation-framework\Scripts principais" -Recurse -Force
}

Write-Host "✅ Limpeza concluída!" -ForegroundColor Green
```

### **Linux/Mac (Bash)**

```bash
#!/bin/bash
# Execute na raiz do projeto

cd "rom-translation-framework"

# 1. Remove cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# 2. Remove backups
find . -name "*.backup_*" -delete

# 3. Remove duplicatas
rm -f core/gemini_translator.py
rm -f core/parallel_translator.py
rm -f core/translation_engine.py
rm -f core/translator_engine.py

# 4. Remove obsoletos interface/
rm -f interface/gui_translator.py
rm -f interface/pointer_scanner.py
rm -f interface/memory_mapper.py
rm -f interface/generic_snes_extractor.py
rm -f interface/integration_patch.py
rm -f interface/tempCodeRunnerFile.py

# 5. Remove duplicatas utils/
rm -f utils/license_guard.py
rm -f utils/cuda_optimizer.py

# 6. Remove docs obsoletos
rm -f docs/7_DAY_ROADMAP.md
rm -f docs/BUG_FIX_DELIVERY.md
rm -f docs/CHANGELOG.md
rm -f docs/COMPLETE_GUIDE.txt
rm -f docs/LAUNCH_STRATEGY.md
rm -f docs/MANUAL_USO.md
rm -f docs/PROJECT_ANALYSIS_REPORT.md
rm -f docs/README.txt
rm -f docs/RELATORIO_CORRECOES.md
rm -f docs/TECHNICAL_MANUAL.txt

# 7. Remove PDF
rm -f MANUAL_USO.pdf

# 8. Limpa dummy_pc_game
rm -f dummy_pc_game/extracted_texts_pc.json
rm -f dummy_pc_game/test_translations.json
rm -rf dummy_pc_game/translation_output

# 9. Limpa ROMs outputs
rm -f "ROMs/Super Nintedo/*_extracted_texts.txt"
rm -f "ROMs/Super Nintedo/*_optimized.txt"
rm -f "ROMs/Super Nintedo/*_translated.txt"

# 10. Remove Scripts principais se vazia
[ -z "$(ls -A 'Scripts principais')" ] && rmdir "Scripts principais"

echo "✅ Limpeza concluída!"
```

---

## 📋 ESTRUTURA FINAL IDEAL

```
PROJETO_V5_OFICIAL/
├── rom-translation-framework/
│   ├── core/                     [13 arquivos .py - Sistema principal]
│   │   ├── charset_inference.py
│   │   ├── compression_detector.py
│   │   ├── encoding_detector.py
│   │   ├── file_format_detector.py
│   │   ├── pc_game_scanner.py
│   │   ├── pc_pipeline.py
│   │   ├── pc_safe_reinserter.py
│   │   ├── pc_text_extractor.py
│   │   ├── pointer_scanner.py
│   │   ├── rom_analyzer.py
│   │   ├── safe_reinserter.py
│   │   ├── text_scanner.py
│   │   ├── universal_pipeline.py
│   │   └── __init__.py
│   │
│   ├── interface/                [3 arquivos .py - GUI e API]
│   │   ├── interface_tradutor_final.py
│   │   ├── gemini_api.py
│   │   └── __init__.py
│   │
│   ├── tools/                    [5 arquivos .py - Ferramentas]
│   ├── security/                 [2 arquivos .py - Segurança]
│   ├── utils/                    [1 arquivo .py - Utilitários]
│   │
│   ├── docs/                     [8 arquivos .md - Docs essenciais]
│   │   ├── 00_START_HERE.md
│   │   ├── BACKEND_EVOLUTION_SUMMARY.md
│   │   ├── GUI_INTEGRATION_PC.md
│   │   ├── INTEGRATION_GUIDE.md
│   │   ├── PC_GAMES_IMPLEMENTATION.md
│   │   ├── PC_GAMES_MODULES_TODO.md
│   │   ├── QUICK_REFERENCE.md
│   │   └── TECHNICAL_ARCHITECTURE.md
│   │
│   ├── data/                     [Dados de configuração]
│   ├── examples/                 [Exemplos de config]
│   ├── dummy_pc_game/            [Jogo de teste limpo]
│   ├── ROMs/                     [OPCIONAL - apenas para teste local]
│   │
│   ├── .gitignore
│   ├── LICENSE
│   ├── QUICK_START.md
│   ├── test_encoding_detector.py
│   └── estrutura_projeto.txt
│
└── PROJETO_CLEANUP_GUIDE.md     [Este arquivo]
```

---

## ⚠️ AVISOS IMPORTANTES

### **Antes de Deletar**

1. ✅ **Faça backup completo do projeto**
2. ✅ **Teste os módulos principais antes de deletar**
3. ✅ **Verifique se arquivos .json de config estão sendo usados**

### **Sobre ROMs**

⚠️ **Se for compartilhar projeto publicamente**:
- ❌ DELETAR todas as ROMs de `ROMs/`
- ✅ Adicionar `ROMs/` ao `.gitignore`
- ✅ Documentar que usuário deve fornecer próprias ROMs legais

### **Recuperação de Arquivos**

Se deletar acidentalmente:
```bash
# Git (se em repositório)
git checkout -- arquivo_deletado.py

# Windows (Lixeira)
# Restaurar da Lixeira

# Linux/Mac
# Verificar se tem .Trash ou Time Machine
```

---

## 📈 GANHOS ESPERADOS

**Antes da limpeza**:
- 📦 ~100+ arquivos
- 💾 ~8-10 MB (com PDF e cache)
- ⚠️ 15+ duplicatas
- ❌ Cache Python ocupando espaço

**Depois da limpeza**:
- ✅ ~50 arquivos essenciais
- ✅ ~2-3 MB (sem PDF/cache)
- ✅ 0 duplicatas
- ✅ Estrutura clara e organizada
- ✅ Fácil de navegar e manter

---

**Recomendação Final**: Execute o script de limpeza e mantenha apenas arquivos essenciais. Seu projeto ficará **profissional, limpo e fácil de manter**.
