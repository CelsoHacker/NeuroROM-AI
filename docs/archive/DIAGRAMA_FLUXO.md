# 🎯 Diagrama de Fluxo - Como Traduzir Seu Jogo

## 📋 Fluxo Simplificado

```
INÍCIO
  │
  ├─ Você tem arquivo de tradução?
  │   │
  │   ├─ SIM → Prossiga
  │   └─ NÃO → Extraia textos primeiro (use outra ferramenta)
  │
  ├─ O arquivo tem mais de 100.000 linhas?
  │   │
  │   ├─ SIM → OTIMIZE PRIMEIRO! 🚀
  │   │         │
  │   │         └─ python otimizar_arquivo_traducao.py seu_arquivo.txt
  │   │                 │
  │   │                 └─ Use arquivo _unique.txt gerado
  │   │
  │   └─ NÃO → Prossiga direto
  │
  ├─ Abra a interface
  │   │
  │   └─ python rom-translation-framework/interface/interface_tradutor_final.py
  │
  ├─ Escolha o MODO de tradução
  │   │
  │   ├─ 🤖 Auto (Gemini → Ollama) ← RECOMENDADO!
  │   │   │
  │   │   └─ Começa rápido (Gemini), termina tudo (Ollama)
  │   │       Nunca para por falta de quota
  │   │
  │   ├─ ⚡ Online Gemini
  │   │   │
  │   │   └─ Muito rápido mas limitado (20 requisições/dia)
  │   │       Para se quota esgotar
  │   │
  │   ├─ 🐌 Offline Ollama
  │   │   │
  │   │   └─ Mais lento mas 100% ilimitado e offline
  │   │       3-4 horas para 755k linhas
  │   │
  │   └─ 🌐 Online DeepL
  │       │
  │       └─ Requer conta paga
  │
  ├─ Configure Workers
  │   │
  │   └─ Recomendado: 3 workers (usa GPU melhor)
  │
  ├─ Carregue seu arquivo
  │   │
  │   └─ Use arquivo _unique.txt se otimizou
  │
  ├─ Clique "TRADUZIR COM IA"
  │   │
  │   └─ Acompanhe progresso
  │       │
  │       ├─ GPU muito quente? → Use botão ⏹️ PARAR
  │       ├─ Quer pausar? → Use botão ⏹️ PARAR
  │       └─ Deixe terminar → Aguarde conclusão
  │
  └─ TRADUÇÃO COMPLETA! ✅
      │
      └─ Arquivo traduzido salvo automaticamente
```

---

## 🎯 Decisão Rápida: Qual Modo Usar?

```
╔═══════════════════════════════════════════════════════════════════╗
║                    QUAL MODO ESCOLHER?                            ║
╚═══════════════════════════════════════════════════════════════════╝

Você tem internet?
    │
    ├─ NÃO → Use 🐌 Offline Ollama
    │         (único que funciona sem internet)
    │
    └─ SIM → Continue
              │
              ├─ Tem API Key do Gemini?
              │   │
              │   ├─ NÃO → Use 🐌 Offline Ollama
              │   │         (100% grátis, ilimitado)
              │   │
              │   └─ SIM → Continue
              │             │
              │             ├─ Quota do Gemini já esgotou hoje?
              │             │   │
              │             │   ├─ SIM → Use 🐌 Offline Ollama OU
              │             │   │         🤖 Auto (vai usar só Ollama)
              │             │   │
              │             │   └─ NÃO → Continue
              │             │             │
              │             │             └─ Quantos textos vai traduzir?
              │             │                 │
              │             │                 ├─ < 4.000 textos
              │             │                 │   └─ Use ⚡ Online Gemini
              │             │                 │       (completa em minutos!)
              │             │                 │
              │             │                 └─ > 4.000 textos
              │             │                     └─ Use 🤖 Auto
              │             │                         (melhor dos 2 mundos)
```

---

## 🔄 Fluxo do Modo Auto (Híbrido)

```
╔═══════════════════════════════════════════════════════════════════╗
║              COMO FUNCIONA O MODO AUTO                            ║
╚═══════════════════════════════════════════════════════════════════╝

INÍCIO (Modo Auto)
  │
  ├─ Verifica disponibilidade
  │   │
  │   ├─ Gemini disponível? ✅
  │   └─ Ollama disponível? ✅
  │
  ├─ FASE 1: Usa Gemini (RÁPIDO)
  │   │
  │   ├─ Traduz até quota esgotar
  │   │   │
  │   │   └─ Velocidade: 1-2 segundos por batch
  │   │       GPU: 0% (API remota)
  │   │       Temperatura: Normal (~50°C)
  │   │
  │   └─ Quota esgotou? → Próxima fase
  │
  ├─ MUDANÇA AUTOMÁTICA 🔄
  │   │
  │   └─ 🟡 Sistema detecta erro 429
  │       "⚠️ Quota Gemini esgotada - mudando para Ollama"
  │
  ├─ FASE 2: Usa Ollama (LENTO MAS ILIMITADO)
  │   │
  │   └─ Traduz todo o resto
  │       │
  │       └─ Velocidade: 10-30 segundos por batch
  │           GPU: 30-94% (processamento local)
  │           Temperatura: 60-70°C
  │
  └─ FIM: TRADUÇÃO 100% COMPLETA ✅
      │
      └─ Estatísticas:
          • Gemini: 4.000 textos (rápido)
          • Ollama: 751.306 textos (resto)
          • Total: 755.306 textos
          • Tempo: 3-4 horas
          • Custo: R$ 0,00
```

---

## ⏸️ Fluxo do Botão PARAR

```
╔═══════════════════════════════════════════════════════════════════╗
║                QUANDO USAR O BOTÃO PARAR                          ║
╚═══════════════════════════════════════════════════════════════════╝

Durante tradução...
  │
  ├─ Motivo para parar?
  │   │
  │   ├─ GPU muito quente (> 75°C)
  │   ├─ Precisa usar o PC para outra coisa
  │   ├─ Quer dar pausa
  │   └─ Vai desligar/reiniciar
  │
  ├─ Clique em: ⏹️ PARAR TRADUÇÃO
  │   │
  │   └─ Janela de confirmação:
  │       "⚠️ Tem certeza que deseja PARAR?"
  │       │
  │       ├─ [NÃO] → Continua traduzindo
  │       │
  │       └─ [SIM] → Para tradução
  │                   │
  │                   └─ Sistema salva progresso
  │                       ✅ Batch atual completo
  │                       ✅ Traduções salvas
  │                       ✅ Estado preservado
  │
  └─ RETOMAR DEPOIS
      │
      ├─ Abra interface novamente
      ├─ Carregue o MESMO arquivo
      ├─ Clique "TRADUZIR"
      │
      └─ Sistema detecta progresso anterior
          "✅ Retomando de onde parou (batch 523/3777)"
```

---

## 📊 Comparação Visual de Tempo

```
TEMPO PARA TRADUZIR 755.306 LINHAS:

Sequencial (1 texto por vez):
[████████████████████████████████████████████████████] 20 DIAS 😱
0                    10 dias                    20 dias

Paralelo (3 workers, batch 10):
[██] 3-4 HORAS ✅
0    1h    2h    3h    4h

Com otimização (remove duplicatas → 150k linhas):
[█] 1-2 HORAS 🚀
0   30min  1h  1.5h  2h


ECONOMIA: 20 dias → 1-2 horas = 480x MAIS RÁPIDO! 🎉
```

---

## 🌡️ Diagrama de Temperatura

```
TEMPERATURA DA GPU DURANTE TRADUÇÃO:

Fase 1: Gemini (10-15 minutos)
╔════════════════════════════════════════════════════╗
║ Temperatura: 48-52°C                              ║
║ GPU: 0-5%                                         ║
║ Status: ✅ Frio (API remota, não usa GPU local)   ║
╚════════════════════════════════════════════════════╝

Transição automática → Ollama

Fase 2: Ollama (3-4 horas)
╔════════════════════════════════════════════════════╗
║ Temperatura: 60-70°C (média)                      ║
║ GPU: 30-94% (picos)                               ║
║ Status: ✅ Normal (GTX 1060 aguenta até 80°C)     ║
╚════════════════════════════════════════════════════╝

Linha do tempo:
0min  ───[Gemini]──→ 15min ───[Ollama]──────────→ 4h
        50°C                 60°C      70°C      65°C
        ❄️                   🌡️        🔥        🌡️

Dica: Use botão PARAR se passar de 75°C!
```

---

## 💡 Otimização: Antes e Depois

```
ARQUIVO ORIGINAL (755.306 linhas):
╔════════════════════════════════════════════════════════════╗
║  Linha 1: "OK"                                            ║
║  Linha 2: "Cancel"                                        ║
║  Linha 3: "Loading..."                                    ║
║  ...                                                       ║
║  Linha 500: "OK"          ← DUPLICATA!                    ║
║  Linha 501: "Cancel"      ← DUPLICATA!                    ║
║  Linha 502: "OK"          ← DUPLICATA!                    ║
║  ...                                                       ║
║  Linha 755.306: "The End"                                 ║
╚════════════════════════════════════════════════════════════╝
Tempo de tradução: 7 horas
Duplicatas: ~80% (605.306 linhas)

           ↓ python otimizar_arquivo_traducao.py

ARQUIVO OTIMIZADO (150.000 linhas):
╔════════════════════════════════════════════════════════════╗
║  Linha 1: "OK"                 ← Apenas 1 vez!            ║
║  Linha 2: "Cancel"             ← Apenas 1 vez!            ║
║  Linha 3: "Loading..."         ← Apenas 1 vez!            ║
║  ...                                                       ║
║  Linha 150.000: "The End"                                 ║
╚════════════════════════════════════════════════════════════╝
Tempo de tradução: 1.4 horas
Economia: 5.6 horas! ✨

RESULTADO:
✅ Mesmo resultado final
✅ 80% menos tempo
✅ 80% menos uso de GPU
✅ 80% menos temperatura
```

---

## 🎯 Resumo de Comandos

```
┌─────────────────────────────────────────────────────────────┐
│  COMANDOS PRINCIPAIS                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1️⃣ Otimizar arquivo (remove duplicatas):                  │
│     python otimizar_arquivo_traducao.py arquivo.txt        │
│                                                             │
│  2️⃣ Abrir interface:                                        │
│     python rom-translation-framework\interface\            │
│            interface_tradutor_final.py                      │
│                                                             │
│  3️⃣ Testar Ollama:                                          │
│     ollama list                                            │
│     ollama run llama3.2:3b "test"                          │
│                                                             │
│  4️⃣ Ver documentação:                                       │
│     LEIA_PRIMEIRO.md                                       │
│                                                             │
│  5️⃣ Launcher automático (Windows):                         │
│     INICIAR_AQUI.bat                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Checklist Final

```
ANTES DE TRADUZIR:

[ ] Ollama está rodando? (ollama serve)
[ ] Arquivo de textos preparado?
[ ] Arquivo tem > 100k linhas?
    [ ] SIM → Otimize primeiro!
    [ ] NÃO → Pode ir direto
[ ] Tem API Key do Gemini? (opcional)
[ ] PC está ventilado?
[ ] Tem 3-4 horas livres? (ou use botão PARAR quando quiser)

DURANTE TRADUÇÃO:

[ ] Progresso está avançando?
[ ] Temperatura < 75°C?
[ ] GPU funcionando (se Ollama)?
[ ] Logs mostram traduções?

SE ALGO DER ERRADO:

[ ] Use botão ⏹️ PARAR
[ ] Progresso foi salvo?
[ ] Erro apareceu nos logs?
[ ] Consulte documentação (LEIA_PRIMEIRO.md)

APÓS TRADUÇÃO:

[ ] Arquivo traduzido foi salvo?
[ ] Traduções fazem sentido?
[ ] Quer traduzir outro arquivo?
    [ ] SIM → Repita processo
    [ ] NÃO → Pronto! 🎉
```

---

**Criado:** 2025-12-19
**Versão:** ROM Translation Framework v5.3
**Status:** ✅ Sistema completo e funcional

**Dúvidas?** Veja [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md)
