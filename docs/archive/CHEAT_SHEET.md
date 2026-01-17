# 📋 Cheat Sheet - ROM Translation Framework v5.3

> **Referência rápida de 1 página - Imprima e cole na parede!** 📌

---

## 🚀 INÍCIO RÁPIDO (30 SEGUNDOS)

```bash
# Windows
INICIAR_AQUI.bat

# Linux/Mac
python rom-translation-framework/interface/interface_tradutor_final.py
```

**Configure:** Modo `🤖 Auto` → Workers `3` → Carregue arquivo → **TRADUZIR**

---

## 🎯 COMANDOS ESSENCIAIS

| Comando | Função |
|---------|--------|
| `python verificar_sistema.py` | Verifica se tudo está OK |
| `python otimizar_arquivo_traducao.py arquivo.txt` | Remove duplicatas (80% redução!) |
| `python rom-translation-framework/interface/interface_tradutor_final.py` | Abre interface gráfica |
| `ollama serve` | Inicia Ollama (outro terminal) |
| `ollama list` | Lista modelos instalados |

---

## 🤖 MODOS DE TRADUÇÃO

| Modo | Quando Usar | Velocidade | Quota | GPU |
|------|-------------|------------|-------|-----|
| **🤖 Auto** | **SEMPRE (padrão)** | Rápido→Lento | 20→∞ | 0%→60% |
| ⚡ Gemini | < 4.000 textos | Muito rápido | 20/dia | 0% |
| 🐌 Ollama | Sem internet ou quota esgotada | Lento | ∞ | 60% |

---

## ⚡ ATALHOS DA INTERFACE

| Tecla/Botão | Função |
|-------------|--------|
| **⏹️ PARAR TRADUÇÃO** | Para e salva progresso |
| `Workers: 3` | Melhor performance |
| `Cache: ✅` | Economiza quota (ative!) |
| `Modo: 🤖 Auto` | Recomendado sempre |

---

## 📊 ESTIMATIVAS DE TEMPO

| Textos | Gemini | Ollama | Auto (otimizado) |
|--------|--------|--------|------------------|
| 1.000 | 25s | 20min | 25s |
| 5.000 | 2min | 1.5h | 10min |
| 100.000 | - | 20h | 2h |
| 755.306 | - | 20 dias | **1.5h** ⚡ |

**Dica:** Use otimizador primeiro! (`python otimizar_arquivo_traducao.py`)

---

## 🌡️ TEMPERATURA GPU

| Modo | Temperatura | Seguro? |
|------|-------------|---------|
| Gemini | 48-52°C | ✅ |
| Ollama | 60-70°C | ✅ (até 80°C) |
| Auto | 50°C→70°C | ✅ |

**Se > 75°C:** Clique ⏹️ PARAR e aguarde esfriar

---

## 🛠️ SOLUÇÃO RÁPIDA DE PROBLEMAS

| Problema | Solução |
|----------|---------|
| ❌ Quota esgotada | Use modo `🤖 Auto` (muda para Ollama) |
| ❌ Ollama não roda | Execute: `ollama serve` |
| ❌ GPU muito quente | Clique ⏹️ PARAR, aguarde 30min |
| ❌ Tradução muito lenta | Otimize arquivo primeiro |
| ❌ Erro de import | Execute: `python verificar_sistema.py` |

---

## 📈 FLUXO OTIMIZADO

```
1. Otimize: python otimizar_arquivo_traducao.py arquivo.txt
   └─ Reduz 80% das linhas (remove duplicatas)

2. Abra: INICIAR_AQUI.bat
   └─ Escolha opção [1]

3. Configure:
   ├─ Modo: 🤖 Auto
   ├─ Workers: 3
   └─ Carregue: arquivo_unique.txt

4. Traduza:
   └─ Clique "TRADUZIR COM IA"

5. Aguarde:
   └─ 1-2 horas para 150k linhas
   └─ Pode usar ⏹️ PARAR a qualquer momento

6. Pronto!
   └─ arquivo_unique_traduzido.txt
```

---

## 📚 DOCUMENTAÇÃO RÁPIDA

| Dúvida | Arquivo |
|--------|---------|
| Como começar? | [README.md](README.md) |
| Guia completo | [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) |
| Arquivo grande | [GUIA_OTIMIZACAO_RAPIDA.md](GUIA_OTIMIZACAO_RAPIDA.md) |
| GPU esquenta? | [RELATORIO_OLLAMA_GPU.md](RELATORIO_OLLAMA_GPU.md) |
| Modo Auto | [GUIA_MODO_HIBRIDO.md](GUIA_MODO_HIBRIDO.md) |
| Índice geral | [INDICE_COMPLETO.md](INDICE_COMPLETO.md) |

---

## 🎯 REGRAS DE OURO

1. ✅ **SEMPRE** otimize arquivos > 100k linhas
2. ✅ **SEMPRE** use modo `🤖 Auto` (melhor opção)
3. ✅ **SEMPRE** configure Workers: `3`
4. ✅ **SEMPRE** ative cache de traduções
5. ✅ **NUNCA** delete arquivos `.json` (são checkpoints!)
6. ✅ Use ⏹️ PARAR se GPU > 75°C

---

## 💰 CUSTOS

| Modo | Custo/dia | Limite |
|------|-----------|--------|
| Gemini Free | R$ 0,00 | 4.000 textos |
| Ollama | R$ 0,00 | ∞ ilimitado |
| Auto | R$ 0,00 | ∞ ilimitado |
| Gemini Pago | ~$2-5 | Muito maior |

**Total:** R$ 0,00 para uso normal! 🎉

---

## 🔑 ATALHOS DE TECLADO (Interface)

| Tecla | Ação |
|-------|------|
| `Ctrl+O` | Abrir arquivo |
| `Ctrl+S` | Salvar tradução |
| `Ctrl+Q` | Sair |
| `Esc` | Cancelar operação |

---

## 📞 VERIFICAÇÃO RÁPIDA

Antes de traduzir, confirme:

```bash
python verificar_sistema.py
```

**Se aparecer "✅ EXCELENTE"** → Pode traduzir!

**Se aparecer "❌ ERRO"** → Veja mensagens e corrija

---

## 🎮 EXEMPLO REAL (755k LINHAS)

```
📊 ANTES:
   Arquivo: 755.306 linhas
   Tempo estimado: 20 dias (sequencial)

🚀 DEPOIS (com otimização):
   1. Otimizou: 30s → 150.000 linhas (-80%)
   2. Traduziu (Auto): 1h 24min
   TOTAL: ~1h 25min

📉 ECONOMIA: 478 horas! (19.9 dias)
```

---

## ✅ CHECKLIST PRÉ-TRADUÇÃO

- [ ] Python 3.8+ instalado
- [ ] Dependências instaladas (`pip install PyQt6 requests google-generativeai`)
- [ ] Ollama rodando (se usar modo Ollama/Auto)
- [ ] Arquivo de entrada preparado
- [ ] Arquivo otimizado (se > 100k linhas)
- [ ] API Key Gemini configurada (se usar Gemini/Auto)
- [ ] Espaço livre > 5GB
- [ ] Verificação: `python verificar_sistema.py` ✅

---

## 🎉 DICA FINAL

**Para traduzir HOJE em poucas horas:**

```bash
# 1. Otimize (30 segundos)
python otimizar_arquivo_traducao.py jogo.txt

# 2. Traduza (1-2 horas)
INICIAR_AQUI.bat
→ Opção [1]
→ Modo: 🤖 Auto
→ Carregue: jogo_unique.txt
→ TRADUZIR

# 3. Pronto! ✨
```

---

**Versão:** 5.3 | **Data:** 2025-12-19 | **Status:** ✅ Pronto

**Mais info:** [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) | **Dúvidas:** [INDICE_COMPLETO.md](INDICE_COMPLETO.md)
