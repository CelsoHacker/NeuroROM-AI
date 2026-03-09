# 🔬 Sistema Forense Corrigido - ROM Translation Framework

## 🎯 Visão Geral

Sistema profissional de análise forense de arquivos de jogos com **assinaturas REAIS** e **métricas honestas**.

## ✅ Correções Implementadas

### 1. Assinaturas REAIS (Magic Bytes Validados)

❌ **ANTES:** Strings fictícias como `"UnityPlayer.dll"`
✅ **AGORA:** Magic bytes oficiais como `b'UnityFS'`

### 2. Métricas Honestas

❌ **ANTES:** Precisão de 98%-99,2% inventada
✅ **AGORA:** Métricas calculadas apenas com testes REAIS

### 3. Fluxo Lógico Correto

❌ **ANTES:** "Layer -1" confuso
✅ **AGORA:** Forense → Extração → Processamento

## 📁 Estrutura de Arquivos

```
rom-translation-framework/
├── core/
│   └── forensic_scanner.py          # Sistema forense corrigido
├── examples/
│   └── test_forensic_scanner.py     # Exemplos de uso
└── docs/
    └── FORENSIC_SCANNER_GUIDE.md    # Documentação completa
```

## 🚀 Uso Rápido

### Análise Forense de Arquivo

```python
from core.forensic_scanner import scan_file

# Escanear arquivo
result = scan_file("game.exe")

# Ver detecções
for detection in result['detections']:
    print(detection.description)
```

### Extração Completa de Texto

```python
from core.forensic_scanner import extract_text_from_file

# Processar arquivo (pipeline completo)
result = extract_text_from_file("game.exe")

# Salvar textos
if result['success']:
    with open('output.txt', 'w', encoding='utf-8') as f:
        for text in result['texts']:
            f.write(text + '\n')
```

### Linha de Comando

```bash
# Escanear arquivo
python core/forensic_scanner.py "C:\Games\MeuJogo\game.exe"

# Executar exemplos interativos
python examples/test_forensic_scanner.py
```

## 🔍 Assinaturas Implementadas

### Engines de Jogo (5 assinaturas)
- Unity: `UnityFS`, `UnityWeb`
- Unreal: `.pak v3`, `.pak v4`

### Instaladores (3 assinaturas)
- Inno Setup
- NSIS
- Genérico (heurística)

### Executáveis (4 assinaturas)
- Windows PE (`MZ`)
- Linux ELF (`\x7fELF`)
- macOS Mach-O (32/64-bit)

### Compactadores (5 assinaturas)
- ZIP, RAR v4/v5, 7-Zip, GZIP

### Jogos Específicos (4+ assinaturas)
- NES ROM
- RPG Maker 2000/2003/VX/MV
- GameMaker Studio

**Total:** 15+ assinaturas REAIS validadas

## 📊 Sistema de Métricas Honesto

```python
from core.forensic_scanner import ForensicScannerReal, HonestMetrics, FileType

scanner = ForensicScannerReal()
metrics = HonestMetrics()

# Adicionar testes REAIS
metrics.add_test_case("unity_game.unity3d", [FileType.UNITY_ASSET_BUNDLE])
metrics.add_test_case("setup.exe", [FileType.INNO_SETUP])

# Calcular métricas (apenas se houver testes)
results = metrics.run_tests(scanner)

if results['total_tests'] > 0:
    print(f"Precisão: {results['precision']:.1%}")
    print(f"⚠️  Baseado em {results['total_tests']} testes")
```

## 📖 Documentação

- **Guia Completo:** [docs/FORENSIC_SCANNER_GUIDE.md](docs/FORENSIC_SCANNER_GUIDE.md)
- **Exemplos:** [examples/test_forensic_scanner.py](examples/test_forensic_scanner.py)
- **Código-fonte:** [core/forensic_scanner.py](core/forensic_scanner.py)

## 🔬 Arquitetura

### Fluxo de Processamento

```
┌─────────────────────────┐
│ 1. ForensicScannerReal  │  ← Detecta tipo por magic bytes
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│ 2. Decisão por Tipo     │  ← Escolhe handler específico
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│ 3. Extração Específica  │  ← Extrai strings validadas
└─────────────────────────┘
```

### Classes Principais

1. **ForensicScannerReal**
   - Detecta tipo de arquivo por assinaturas
   - Valida magic bytes
   - Retorna detecções com confiança

2. **GameTextExtractorCorrected**
   - Processa arquivo baseado no tipo
   - Extrai strings ASCII e UTF-16 LE
   - Valida texto de jogo

3. **HonestMetrics**
   - Calcula métricas REAIS
   - Requer ground truth
   - Não inventa estatísticas

## 🧪 Testes

### Executar Exemplos

```bash
# Menu interativo
python examples/test_forensic_scanner.py

# Opções:
# 1. Scan simples
# 2. Extração de texto
# 3. Métricas honestas
# 4. Funções de conveniência
# 5. Lista de assinaturas
```

### Adicionar Casos de Teste

```python
from core.forensic_scanner import HonestMetrics, FileType

metrics = HonestMetrics()

# Adicione SEUS arquivos reais
metrics.add_test_case(
    "C:\\Games\\MeuJogo\\data.unity3d",
    [FileType.UNITY_ASSET_BUNDLE]
)

# Execute testes
results = metrics.run_tests(scanner)
```

## ⚠️ Avisos Importantes

### 1. Instaladores
Se detectar instalador, o sistema avisa:
```
⚠️  ARQUIVO É UM INSTALADOR
💡 RECOMENDAÇÃO: Execute o instalador e selecione a pasta do jogo
```

### 2. Arquivos Compactados
```
📦 ARQUIVO COMPACTADO DETECTADO
💡 RECOMENDAÇÃO: Extraia e selecione a pasta extraída
```

### 3. Métricas
```
⚠️  NOTA: Métricas são estimativas baseadas em N testes
Para métricas mais precisas, adicione mais casos de teste
```

## 🎓 Princípios Científicos

1. **Verificabilidade**
   - Todas as assinaturas são documentadas
   - Código pode ser validado

2. **Honestidade**
   - Não inventa estatísticas
   - Avisa sobre limitações

3. **Reprodutibilidade**
   - Mesma entrada = mesma saída
   - Testes podem ser repetidos

## 📚 Referências

- [Wikipedia - Magic number (programming)](https://en.wikipedia.org/wiki/Magic_number_(programming))
- [Gary Kessler's File Signature Table](https://www.garykessler.net/library/file_sigs.html)
- [Microsoft PE Format](https://docs.microsoft.com/en-us/windows/win32/debug/pe-format)
- [Unity Manual - AssetBundles](https://docs.unity3d.com/Manual/AssetBundlesIntro.html)

## 👨‍💻 Autor

**Celso** - Cientista da Computação
Sistema corrigido conforme feedback científico

## 📝 Changelog

### Versão 1.0 (2026-01-06)
- ✅ Implementadas assinaturas REAIS (15+ validadas)
- ✅ Sistema de métricas honesto
- ✅ Fluxo lógico corrigido
- ✅ Validação de magic bytes
- ✅ Extração de strings com filtros
- ✅ Documentação completa

---

## 🚀 Próximos Passos

1. Testar com seus arquivos reais
2. Adicionar mais assinaturas conforme necessário
3. Validar métricas com ground truth
4. Reportar bugs ou sugestões

**Sistema pronto para uso profissional!** ✅
