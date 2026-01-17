# 🔥 Guia Rápido - Runtime Text Capture (RTCE)

## Como Usar em 5 Passos

### 1️⃣ Abrir Emulador com Jogo **PRIMEIRO**
```
📌 IMPORTANTE: O emulador DEVE estar rodando ANTES!

Exemplo:
- SNES: snes9x-x64.exe → Carregar Super Mario World.smc
- PS1: epsxe.exe → Carregar Final Fantasy VII.bin

💡 Se em tela cheia: Alt+Enter para modo janela
```

### 2️⃣ Abrir NeuroROM AI
```
1. Selecione a plataforma (SNES, PS1, etc)
2. Clique em "⚡ Capturar Runtime"
3. ✅ Leia o aviso e clique OK
```

### 3️⃣ Configurar Captura
```
✅ Sistema detecta emuladores automaticamente
✅ Escolha o processo na lista
✅ Configure duração (padrão: 5 minutos)
✅ Clique em "▶️ Iniciar Captura"
```

### 4️⃣ Jogar Normalmente
```
✅ Captura em andamento!
✅ Pode voltar ao jogo e jogar normalmente
✅ Pode usar tela cheia (Alt+Enter)

Durante a captura:
🎮 Navegue pelos menus
🎮 Abra diálogos
🎮 Troque de telas
🎮 Entre em batalhas

O sistema captura TUDO automaticamente!
```

### 5️⃣ Resultado
```
✅ Arquivo salvo: seu_jogo_rtce_texts.txt
✅ Formato: [0xOFFSET] texto
✅ Pronto para Otimizar → Traduzir
```

---

## 📊 Comparação: RTCE vs OCR

| Método | Captura | Qualidade | Quando Usar |
|--------|---------|-----------|-------------|
| **OCR** (ROM) | Gráficos (tiles) | 85-95% | Textos fixos na ROM |
| **RTCE** (Runtime) | Strings (memória) | 95-99% | Textos dinâmicos |
| **Híbrido** | Ambos | 99%+ | Máxima precisão |

---

## 🎯 Exemplo Real

### Super Mario World (SNES)

**Método Antigo (OCR):**
```
[0x7E1A20] St4rt G4me    ← Erro OCR (4 em vez de a)
[0x7E1A40] C0ntinue      ← Erro OCR (0 em vez de o)
```

**Método Novo (RTCE):**
```
[0x7E1A20] Start Game    ← 100% correto
[0x7E1A40] Continue      ← 100% correto
[0x7E1A60] Options       ← Capturado da memória
[0x7E2100] Level 1-1     ← Texto dinâmico
```

---

## ⚙️ Requisitos

```bash
# Instalar dependência
pip install psutil

# Já incluído no projeto:
rtce_core/
├── memory_scanner.py
├── text_heuristics.py
├── platform_profiles.py
├── rtce_engine.py
└── orchestrator.py
```

---

## 🚀 Plataformas Suportadas

✅ SNES (Super Nintendo)
✅ NES (Nintendo)
✅ N64 (Nintendo 64)
✅ GBA (Game Boy Advance)
✅ NDS (Nintendo DS)
✅ Genesis/Mega Drive
✅ PS1 (PlayStation 1)
✅ PS2 (PlayStation 2)
✅ PC Games (Windows)

---

## 💡 Dicas Pro

### Capturar Mais Textos
- Deixe captura rodando por 10-15 minutos
- Complete o tutorial do jogo
- Visite todas as áreas
- Abra todos os menus

### Combinar com OCR
1. Extraia com OCR (botão verde)
2. Capture com RTCE (botão roxo)
3. Otimize ambos
4. Sistema remove duplicatas automaticamente

### Troubleshooting
❌ "Emulador não encontrado"
   → Certifique-se que o emulador está rodando

❌ "Nenhum texto capturado"
   → Navegue pelos menus do jogo
   → Aumente a duração da captura

❌ "psutil não instalado"
   → Execute: pip install psutil

---

**Desenvolvido por: Celso**
**Data: 2025-01-12**
