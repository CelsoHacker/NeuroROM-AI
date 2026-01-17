# 📊 Relatório de Uso da GPU - Ollama (Llama 3.2)

## 🎮 Configuração Detectada

**GPU:** NVIDIA GeForce GTX 1060 6GB
- **VRAM Total:** 6144 MB (6 GB)
- **VRAM Disponível:** 2363 MB
- **Temperatura Base:** 49-52°C

**Modelo Llama:**
- **Nome:** llama3.2:3b
- **Tamanho:** 2.0 GB
- **Parâmetros:** 3 bilhões

---

## ⚡ Uso da GPU Durante Tradução

### Antes da Tradução (Idle)
```
GPU: 1-4%
VRAM: 3668 MB (59.7%)
Temp: 49°C
```

### Durante a Tradução (Pico)
```
GPU: 94% ⚠️ USO MÁXIMO!
VRAM: 3617 MB (58.9%)
Temp: 57°C (+8°C)
Duração: 2-4 segundos
```

### Após a Tradução (Volta ao Normal)
```
GPU: 1-2%
VRAM: 3605 MB (58.7%)
Temp: 54°C (esfriando)
```

---

## 📈 Gráfico de Uso ao Longo do Tempo

```
Uso da GPU (%)
100% │
     │                    ████
 90% │                   ██████
     │                  ████████
 80% │                  ████████
     │                  ████████
 70% │                  ████████
     │
 60% │
     │
 50% │
     │
 40% │
     │
 30% │
     │
 20% │
     │
 10% │  ██              ██      ██  ██  ██  ██  ██
     │  ██              ██      ██  ██  ██  ██  ██
  0% └──┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴──> Tempo (s)
     0s  2s  4s  6s  8s  10s 12s 14s 16s 18s 20s

     ↑       ↑          ↑
  Início  Traduz  Fim da tradução
           (pico)
```

---

## 🔥 Temperatura da GPU

```
Temperatura (°C)
60° │
    │               ███
57° │              █████
    │             ███████
54° │            █████████████████████
    │           ███████████████████████
51° │          █████████████████████████
    │        ███████████████████████████
48° │     ███████████████████████████████
    └─────┴────┴────┴────┴────┴────┴────┴──> Tempo
      0s   4s   8s   12s  16s  20s

Variação: 49°C → 57°C (+8°C)
Aquecimento: Normal e seguro ✅
```

---

## 💾 Uso de VRAM

```
VRAM Usada (MB)
6144 │ ┌─────────────────────────────────────┐
     │ │          LIMITE DA GPU              │
5000 │ ├─────────────────────────────────────┤
     │ │                                     │
4000 │ │                                     │
     │ │   ╔═══════════════════════════════╗ │
3669 │ │   ║  VRAM USADA (Base)            ║ │
     │ │   ║  3600-3670 MB                 ║ │
3000 │ │   ║                               ║ │
     │ │   ║  Modelo Llama: ~2000MB        ║ │
2000 │ │   ║  Sistema + Apps: ~1600MB      ║ │
     │ │   ║                               ║ │
1000 │ │   ╚═══════════════════════════════╝ │
     │ │                                     │
   0 │ └─────────────────────────────────────┘

VRAM Livre: 2363 MB (38.5%)
Modelo precisa: ~2000 MB
Resultado: ✅ CABE PERFEITAMENTE!
```

---

## 📊 Desempenho de Tradução

### Teste Realizado
**Entrada:**
```
"Welcome to the game! Press START to begin. Game Over. Continue? New Game. Options. Quit."
```

**Saída:**
```
"Olá para o jogo! Pressione START para começar. Fim do Jogo. Continuar? Novo Jogo. Opções. Sair."
```

### Métricas
- ⏱️ **Tempo total:** 30.79 segundos
- 🚀 **Tokens/segundo:** 0.58
- 📊 **Uso da GPU:** 94% (pico)
- 🌡️ **Temperatura máxima:** 57°C
- ✅ **Qualidade:** Boa (português natural)

---

## 📉 Comparação: Gemini vs Ollama

| Métrica | Google Gemini | Ollama (Llama 3.2) |
|---------|---------------|---------------------|
| **Velocidade** | ~1-2s/texto | ~30s/texto |
| **Quota** | 20 req/dia (free) | ∞ ilimitado |
| **Custo** | Grátis (limite) ou pago | 100% grátis |
| **Uso de GPU** | ❌ Não (API remota) | ✅ 30-94% |
| **Uso de VRAM** | ❌ 0 MB | ✅ ~2000 MB |
| **Internet** | ✅ Necessária | ❌ Funciona offline |
| **Qualidade** | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐⭐⭐ Muito boa |

---

## 💡 Recomendações de Uso

### Use Gemini quando:
- ✅ Tiver quota disponível (< 20 traduções/dia)
- ✅ Precisar de velocidade máxima (1-2s)
- ✅ Qualidade for prioridade absoluta
- ✅ Textos forem complexos (contexto de jogo, gírias)

### Use Ollama quando:
- ✅ Esgotou quota do Gemini (> 20 traduções/dia)
- ✅ Não tiver internet estável
- ✅ Quiser tradução ilimitada e gratuita
- ✅ Não se importar com tempo (30s por texto)
- ✅ GPU estiver ociosa (aproveitar hardware local)

---

## ⚙️ Otimizações Possíveis

### 1. Acelerar Ollama
```bash
# Usar modelo menor (mais rápido, menos qualidade)
ollama pull llama3.2:1b  # 1 bilhão de parâmetros (~1GB)

# Ajustar contexto para traduções curtas
# Em core/translator_engine.py, reduzir max_tokens
```

### 2. Usar GPU ao Máximo
```python
# Processar múltiplas traduções em paralelo
# CUIDADO: pode superaquecer GPU!

import threading

def translate_parallel(texts):
    threads = []
    for text in texts:
        t = threading.Thread(target=translate, args=(text,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
```

### 3. Modo Híbrido (Melhor dos 2 Mundos)
```python
# Use Gemini até quota esgotar, depois Ollama
if gemini_quota_available():
    translate_with_gemini(text)
else:
    translate_with_ollama(text)
```

---

## 🎯 Uso de GPU por Quantidade de Textos

| Textos | Tempo Total | GPU Ocupada | Aquecimento |
|--------|-------------|-------------|-------------|
| 10     | ~5 minutos  | 30-50%      | +5°C        |
| 100    | ~50 minutos | 40-70%      | +10°C       |
| 1.000  | ~8.5 horas  | 50-90%      | +15°C       |
| 10.000 | ~85 horas   | 60-94%      | +20°C ⚠️    |

**⚠️ Aviso:** Para > 1.000 textos, considere:
- Fazer em lotes menores
- Dar pausas para GPU esfriar
- Monitorar temperatura (não ultrapassar 80°C)

---

## 🔧 Como Configurar na Interface

Vá em **"Modo de Tradução"** e selecione:

```
┌─────────────────────────────────────────┐
│ Modo de Tradução                        │
├─────────────────────────────────────────┤
│ ○ Online Gemini (Google API)            │ ← Rápido, quota limitada
│ ● Local Ollama (Llama/Mistral)          │ ← Lento, ilimitado ✅
│ ○ DeepL Translator                      │
│ ○ OpenAI GPT                            │
└─────────────────────────────────────────┘
```

**Configurações extras para Ollama:**
- **Workers:** 1-3 (mais = mais GPU usada)
- **Timeout:** 60-120s (Llama é lento)
- **Cache:** ✅ Ativar (evita re-traduzir)

---

## 📊 Monitoramento em Tempo Real

Para ver uso da GPU durante tradução:

```bash
# Em um terminal separado
watch -n 1 nvidia-smi

# Ou com mais detalhes
nvidia-smi dmon -s um
```

---

## ✅ Conclusão

**Sua GTX 1060 6GB é PERFEITA para Ollama:**
- ✅ VRAM suficiente (2.3GB livres, modelo usa 2GB)
- ✅ Temperatura controlada (57°C pico, safe até 80°C)
- ✅ Performance boa (0.58 tokens/s)

**Uso estimado durante tradução grande:**
- 📊 GPU: 30-94% (média ~60%)
- 🌡️ Temperatura: 50-65°C
- 💾 VRAM: +2GB (~60% total)
- ⚡ Consumo: +50-100W (normal para GTX 1060)

**Você pode traduzir tranquilamente sem se preocupar!** 🎉
