# 🔬 Sistema Forense Corrigido - Guia Completo

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Correções Implementadas](#correções-implementadas)
3. [Assinaturas Reais](#assinaturas-reais)
4. [Fluxo de Processamento](#fluxo-de-processamento)
5. [Uso Básico](#uso-básico)
6. [Métricas Honestas](#métricas-honestas)
7. [Exemplos Práticos](#exemplos-práticos)
8. [Referências](#referências)

---

## 🎯 Visão Geral

O **Sistema Forense Corrigido** é uma implementação profissional de análise forense de arquivos de jogos com as seguintes características:

✅ **Assinaturas REAIS** - Apenas magic bytes oficiais e documentados
✅ **Sem estatísticas inventadas** - Métricas baseadas apenas em testes verificáveis
✅ **Fluxo lógico correto** - Forense → Extração (por tipo) → Processamento
✅ **Código científico** - Validado e verificável

---

## 🔧 Correções Implementadas

### ❌ Problemas Anteriores

1. **Assinaturas Fictícias**
   - Uso de strings como `"UnityPlayer.dll"` (nome de arquivo, não padrão binário)
   - Nunca seriam detectadas em arquivos reais

2. **Estatísticas sem Base**
   - Afirmação de precisão 98%-99,2% sem ground truth
   - Métricas inventadas sem validação

3. **Sistema de Camadas Confuso**
   - "Layer -1" quebrava o fluxo lógico
   - Mistura de responsabilidades

### ✅ Soluções Implementadas

1. **Assinaturas REAIS Validadas**
   ```python
   b'UnityFS': SignatureInfo(
       type=FileType.UNITY_ASSET_BUNDLE,
       description='🎮 Unity Asset Bundle detectado',
       offset=0,
       validation_func=self._validate_unity_fs
   )
   ```
   - Magic bytes oficiais documentados
   - Validação adicional quando necessário

2. **Métricas Honestas**
   ```python
   # Só calcula métricas se houver testes REAIS
   if valid_tests > 0:
       precision = tp / (tp + fp) if (tp + fp) > 0 else 0
       # Sempre avisa que é estimativa
       print(f"⚠️  NOTA: Métricas são estimativas baseadas em {valid_tests} testes")
   ```

3. **Fluxo Correto**
   ```
   1. Análise Forense (ForensicScannerReal)
      ↓
   2. Extração Específica (por tipo detectado)
      ↓
   3. Processamento (GameTextExtractorCorrected)
   ```

---

## 🔍 Assinaturas Reais

### Unity Engine

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `UnityFS` | UNITY_ASSET_BUNDLE | Asset Bundle do Unity |
| `UnityWeb` | UNITY_WEBGL | Build WebGL do Unity |

### Unreal Engine

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `\x1E\x0A\x00\x00` | UNREAL_PAK_V3 | Unreal .pak versão 3 |
| `\x1F\x0A\x00\x00` | UNREAL_PAK_V4 | Unreal .pak versão 4 |

### Instaladores

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `Inno Setup Setup Data` | INNO_SETUP | Instalador Inno Setup |
| `NullsoftInst` | NSIS_INSTALLER | Instalador NSIS |

### Executáveis

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `MZ` | WINDOWS_EXE | Executável Windows PE |
| `\x7fELF` | LINUX_ELF | Executável Linux ELF |
| `\xFE\xED\xFA\xCE` | MACOS_MACH | Executável macOS 32-bit |
| `\xFE\xED\xFA\xCF` | MACOS_MACH | Executável macOS 64-bit |

### Compactadores

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `PK\x03\x04` | ZIP_ARCHIVE | Arquivo ZIP |
| `Rar!\x1a\x07\x00` | RAR_ARCHIVE_V4 | Arquivo RAR v4 |
| `Rar!\x1a\x07\x01\x00` | RAR_ARCHIVE_V5 | Arquivo RAR v5 |
| `7z\xbc\xaf\x27\x1c` | SEVENZIP_ARCHIVE | Arquivo 7-Zip |
| `\x1f\x8b` | GZIP_ARCHIVE | Arquivo GZIP |

### ROMs e Jogos Específicos

| Magic Bytes | Tipo | Descrição |
|-------------|------|-----------|
| `NES\x1a` | NES_ROM | ROM Nintendo NES |

### Detecção por Nome de Arquivo

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `RPG_RT.ldb` | RPG_MAKER_2000 | RPG Maker 2000/2003 DB |
| `RPG_RT.lmt` | RPG_MAKER_2000 | RPG Maker 2000/2003 Map |
| `game.rgss3a` | RPG_MAKER_VX | RPG Maker VX Ace |
| `data.win` | GAME_MAKER_STUDIO | GameMaker Studio |

**Total:** 15+ assinaturas reais validadas

---

## 🔄 Fluxo de Processamento

### Fluxo Correto

```
┌─────────────────────────────────────────┐
│  1. ANÁLISE FORENSE                     │
│  (ForensicScannerReal)                  │
│                                         │
│  • Lê magic bytes (primeiros 4KB)      │
│  • Compara com assinaturas reais       │
│  • Valida se necessário                │
│  • Retorna detecções                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. DECISÃO POR TIPO                    │
│  (GameTextExtractorCorrected)           │
│                                         │
│  Instalador? → _handle_installer()     │
│  Engine?     → _handle_game_engine()   │
│  Arquivo?    → _handle_archive()       │
│  RPG Maker?  → _handle_rpg_maker()     │
│  Outro?      → _extract_universal()    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. EXTRAÇÃO ESPECÍFICA                 │
│                                         │
│  • Extrai strings ASCII                │
│  • Extrai strings UTF-16 LE            │
│  • Valida texto (_is_valid_game_text)  │
│  • Remove duplicatas                   │
│  • Retorna resultados                  │
└─────────────────────────────────────────┘
```

### Exemplo de Código

```python
from forensic_scanner import GameTextExtractorCorrected

# Criar extrator
extractor = GameTextExtractorCorrected()

# Processar arquivo (pipeline completo)
result = extractor.process_file("game.exe")

if result['success']:
    print(f"Tipo: {result['type']}")
    print(f"Textos: {len(result['texts'])}")

    # Salvar textos
    with open('output.txt', 'w', encoding='utf-8') as f:
        for text in result['texts']:
            f.write(text + '\n')
```

---

## 📖 Uso Básico

### 1. Scan Simples (Apenas Análise Forense)

```python
from forensic_scanner import ForensicScannerReal

scanner = ForensicScannerReal()
result = scanner.scan_file("game.exe")

for detection in result['detections']:
    print(f"{detection.description}")
    print(f"Tipo: {detection.type.value}")
    print(f"Assinatura: {detection.signature}")

    if detection.warning:
        print(f"⚠️  {detection.warning}")
```

### 2. Extração Completa de Texto

```python
from forensic_scanner import GameTextExtractorCorrected

extractor = GameTextExtractorCorrected()
result = extractor.process_file("game.exe")

if result['success']:
    for text in result['texts'][:10]:
        print(text)
```

### 3. Função de Conveniência

```python
from forensic_scanner import scan_file, extract_text_from_file

# Apenas scan
scan_result = scan_file("game.exe")

# Scan + extração
extract_result = extract_text_from_file("game.exe")
```

---

## 📊 Métricas Honestas

### Sistema de Validação

O sistema **NÃO INVENTA** estatísticas. Métricas são calculadas apenas com testes REAIS.

```python
from forensic_scanner import ForensicScannerReal, HonestMetrics, FileType

scanner = ForensicScannerReal()
metrics = HonestMetrics()

# Adicionar casos de teste REAIS
metrics.add_test_case(
    "C:\\Games\\Unity\\data.unity3d",
    [FileType.UNITY_ASSET_BUNDLE]
)

metrics.add_test_case(
    "C:\\Games\\setup.exe",
    [FileType.INNO_SETUP, FileType.WINDOWS_EXE]
)

# Executar testes
results = metrics.run_tests(scanner)

# Métricas calculadas apenas se houver testes válidos
if results['total_tests'] > 0:
    print(f"Precisão: {results['precision']:.1%}")
    print(f"Recall: {results['recall']:.1%}")
    print(f"F1-Score: {results['f1_score']:.1%}")
    print(f"\n⚠️  Baseado em {results['total_tests']} testes")
```

### Métricas Calculadas

- **Precisão (Precision):** `TP / (TP + FP)`
  - Quantas detecções estavam corretas

- **Recall:** `TP / (TP + FN)`
  - Quantos arquivos esperados foram detectados

- **F1-Score:** `2 * (Precision * Recall) / (Precision + Recall)`
  - Média harmônica entre precisão e recall

**IMPORTANTE:** Sempre avisa que são estimativas baseadas em N testes.

---

## 💡 Exemplos Práticos

### Exemplo 1: Detectar Instalador

```python
from forensic_scanner import scan_file

result = scan_file("setup.exe")

for detection in result['detections']:
    if 'INSTALLER' in detection.type.name:
        print(detection.warning)
        # Output: "Extraia o jogo primeiro ou instale-o antes de traduzir"
```

### Exemplo 2: Processar Jogo Unity

```python
from forensic_scanner import extract_text_from_file

result = extract_text_from_file("data.unity3d")

if result['success'] and result['type'] == 'engine_game':
    print(f"Engine: {result['engine']}")
    print(f"Textos: {len(result['texts'])}")

    # Salvar textos
    with open('unity_texts.txt', 'w', encoding='utf-8') as f:
        for text in result['texts']:
            f.write(text + '\n')
```

### Exemplo 3: Validar Detecção

```python
from forensic_scanner import ForensicScannerReal

scanner = ForensicScannerReal()

# Lista de assinaturas disponíveis
print(f"Assinaturas implementadas: {len(scanner.signatures)}")

for signature, info in scanner.signatures.items():
    # Mostra assinatura legível
    if all(32 <= b <= 126 for b in signature):
        sig_display = signature.decode('ascii')
    else:
        sig_display = signature.hex()

    print(f"{info.type.value}: {sig_display}")
```

### Exemplo 4: Script de Linha de Comando

```bash
# Escanear arquivo
python core/forensic_scanner.py game.exe

# Executar exemplos
python examples/test_forensic_scanner.py
```

---

## 📚 Referências

### Documentação de Magic Bytes

- [Wikipedia - Magic number (programming)](https://en.wikipedia.org/wiki/Magic_number_(programming))
- [Gary Kessler's File Signature Table](https://www.garykessler.net/library/file_sigs.html)
- [File Signatures](https://filesignatures.net/)

### Engines de Jogo

- **Unity:** [Unity Manual - AssetBundles](https://docs.unity3d.com/Manual/AssetBundlesIntro.html)
- **Unreal:** [Unreal Engine Documentation - Pak Files](https://docs.unrealengine.com/en-US/SharingAndReleasing/Patching/index.html)
- **RPG Maker:** [RPG Maker Forums - File Formats](https://forums.rpgmakerweb.com/)

### Formatos de Arquivo

- **PE (Windows):** [Microsoft PE Format](https://docs.microsoft.com/en-us/windows/win32/debug/pe-format)
- **ELF (Linux):** [ELF Specification](https://refspecs.linuxfoundation.org/elf/elf.pdf)
- **ZIP:** [PKWARE ZIP Format](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)

---

## ✅ Conclusão

Este sistema forense foi desenvolvido com rigor científico:

1. **Assinaturas verificáveis** - Apenas magic bytes documentados
2. **Métricas honestas** - Sem invenção de estatísticas
3. **Fluxo lógico** - Arquitetura clara e profissional
4. **Código validável** - Pode ser testado e verificado

Para dúvidas ou sugestões, consulte o código-fonte em `core/forensic_scanner.py`.

---

**Autor:** Celso (Cientista da Computação)
**Data:** 2026-01-06
**Versão:** 1.0 (Sistema Corrigido)
