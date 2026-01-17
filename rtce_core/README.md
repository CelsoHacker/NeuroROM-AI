# 🔥 Runtime Text Capture Engine (RTCE)

## Visão Geral

Motor de captura de textos em tempo de execução via leitura externa de memória.

**Não usa código de emuladores. Não distribui emuladores. Apenas lê memória de processos externos.**

## Arquitetura

```
rtce_core/
├── __init__.py              # Exports principais
├── memory_scanner.py        # Leitura de memória (Windows API)
├── text_heuristics.py       # Análise linguística
├── platform_profiles.py     # Perfis de plataforma
├── rtce_engine.py           # Engine principal
├── orchestrator.py          # Orquestrador OCR + RTCE
└── README.md                # Esta documentação
```

## Uso Básico

### Exemplo 1: Scan Único

```python
from rtce_core import RTCEEngine

# Criar engine para SNES
engine = RTCEEngine(platform='SNES')

# Anexar ao emulador (ex: Snes9x)
if engine.attach_to_process('snes9x-x64.exe'):
    # Escanear memória uma vez
    results = engine.scan_once()

    for result in results:
        print(f"{result.offset}: {result.text} (conf: {result.confidence:.2f})")

    engine.detach_from_process()
```

### Exemplo 2: Scan Contínuo

```python
from rtce_core import RTCEEngine

def on_new_text(results):
    for r in results:
        print(f"[NOVO] {r.text}")

with RTCEEngine(platform='SNES') as engine:
    engine.attach_to_process('snes9x-x64.exe')

    # Scan contínuo a cada 1 segundo
    engine.scan_continuous(
        interval=1.0,
        max_iterations=60,
        callback=on_new_text
    )
```

### Exemplo 3: Orquestrador OCR + RTCE

```python
from rtce_core import RTCEEngine, TextCaptureOrchestrator

# Criar orquestrador
orch = TextCaptureOrchestrator()

# Adicionar resultados OCR (do sistema existente)
orch.add_ocr_result({
    'text': 'Start Game',
    'confidence': 0.85,
    'source': 'ocr'
})

# Adicionar resultados RTCE
engine = RTCEEngine(platform='SNES')
engine.attach_to_process('snes9x-x64.exe')
rtce_results = engine.scan_once()

for r in rtce_results:
    orch.add_runtime_result({
        'text': r.text,
        'confidence': r.confidence,
        'offset': r.offset
    })

# Unificar resultados
unified = orch.unify_results()

for u in unified:
    print(f"{u.source.value}: {u.text} (conf: {u.confidence:.2f})")
```

## Plataformas Suportadas

- ✅ SNES (Super Nintendo)
- ✅ NES (Nintendo Entertainment System)
- ✅ N64 (Nintendo 64)
- ✅ GBA (Game Boy Advance)
- ✅ NDS (Nintendo DS)
- ✅ Genesis/Mega Drive
- ✅ Master System
- ✅ Saturn
- ✅ Dreamcast
- ✅ PS1 (PlayStation 1)
- ✅ PS2 (PlayStation 2)
- ✅ PC (Windows)

## Heurística Linguística

O sistema usa análise multi-fator:

1. **Proporção de vogais**: 25%-60% ideal
2. **Caracteres imprimíveis**: >80%
3. **Entropia Shannon**: 2.0-7.0
4. **Classificação**: letra, palavra, frase, menu_string
5. **Score de confiança**: 0.0-1.0

## Formato de Saída

```json
{
  "source": "runtime",
  "offset": "0x7E1A20",
  "text": "Start Game",
  "text_type": "menu_string",
  "confidence": 0.91,
  "metrics": {
    "vowel_ratio": 0.40,
    "printable_ratio": 1.0,
    "entropy": 4.2,
    "length": 10
  },
  "timestamp": 1736695200.0
}
```

## Integração com Pipeline Existente

O RTCE complementa (não substitui) o OCR:

- **OCR**: Para textos gráficos (tiles, sprites)
- **RTCE**: Para textos string (memória)
- **Orquestrador**: Combina ambos para máxima precisão

## Requisitos

- Python 3.8+
- Windows (Linux/macOS em desenvolvimento)
- `psutil` (para detecção de processos)
- `ctypes` (built-in)

## Instalação

```bash
pip install psutil
```

## Limitações Conhecidas

- Atualmente apenas Windows (ReadProcessMemory)
- Emulador deve estar em execução
- Requer permissões de leitura de memória
- Não detecta textos comprimidos/criptografados

## Roadmap

- [ ] Suporte Linux (ptrace)
- [ ] Suporte macOS (task_for_pid)
- [ ] Detecção automática de encoding
- [ ] Análise de strings comprimidas (LZ77, Huffman)
- [ ] Interface gráfica integrada

## Legal

Este código usa técnicas padrão de debug/QA (ReadProcessMemory).
Não distribui, incorpora ou modifica emuladores.
Uso educacional e desenvolvimento de ferramentas de tradução.

---

**Desenvolvido por: Celso**
**Data: 2026-01-12**
**Versão: 1.0.0**
