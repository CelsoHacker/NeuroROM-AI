# 📚 ÍNDICE COMPLETO DA DOCUMENTAÇÃO

**ROM Translation Framework v5 - Guia de Navegação**

---

## 🎯 COMECE AQUI

Se você é novo no framework, comece por estes documentos **NA ORDEM**:

1. **[README.md](README.md)** - Visão geral do framework
2. **[GUIA_VISUAL_RAPIDO.md](GUIA_VISUAL_RAPIDO.md)** - Entenda ROMs vs PC em 1 minuto
3. **[FAQ_CLIENTES.md](FAQ_CLIENTES.md)** - Perguntas frequentes

Depois, escolha o caminho conforme seu tipo de jogo:
- **ROMs de Console** → Use a interface (3 abas)
- **Jogos de PC** → Leia [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md)

---

## 📖 DOCUMENTAÇÃO POR TIPO DE USO

### 🎮 Você Quer Traduzir ROMs de Console (SNES, NES, GBA, etc.)

| Documento | Descrição | Quando Ler |
|-----------|-----------|------------|
| **[README.md](README.md)** | Visão geral e instalação | Primeiro contato |
| **Interface (3 abas)** | Processo automático | Durante tradução |
| **[FAQ_CLIENTES.md](FAQ_CLIENTES.md)** | Dúvidas comuns | Quando tiver problemas |

**Você está pronto!** ROMs de console não precisam de documentação adicional.

---

### 💻 Você Quer Traduzir Jogos de PC

| Documento | Descrição | Quando Ler |
|-----------|-----------|------------|
| **[GUIA_VISUAL_RAPIDO.md](GUIA_VISUAL_RAPIDO.md)** | Diferença ROMs vs PC | Antes de começar |
| **[MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md)** | Guia completo jogos PC | **ESSENCIAL - Leia todo!** |
| **[FAQ_CLIENTES.md](FAQ_CLIENTES.md)** | Seção "Jogos de PC" | Dúvidas específicas |
| **Conversores** (`converter_*.py`) | Scripts específicos | Durante instalação |

**Caminho**: Aba 1 → Aba 2 → Conversor específico → Instalação manual

---

### 🏢 Você Oferece Serviço Comercial de Tradução

| Documento | Descrição | Quando Ler |
|-----------|-----------|------------|
| **[FAQ_CLIENTES.md](FAQ_CLIENTES.md)** | Respostas para clientes | Antes de atender cliente |
| **[MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md)** | Preços sugeridos | Ao fazer orçamento |
| **[GUIA_VISUAL_RAPIDO.md](GUIA_VISUAL_RAPIDO.md)** | Explicar para clientes | Ao educar cliente |
| **Licença Comercial** | Termos de uso | Antes de vender traduções |

**Dica**: Imprima o FAQ e GUIA_VISUAL para mostrar aos clientes!

---

### 🔧 Você é Desenvolvedor/Técnico

| Documento | Descrição | Quando Ler |
|-----------|-----------|------------|
| **[README.md](README.md)** | Estrutura do projeto | Antes de modificar código |
| **[MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md)** | Criar novos conversores | Ao adicionar suporte |
| **Código-fonte** (`core/`, `interface/`) | Implementação | Durante desenvolvimento |
| **[SMW_ULTIMATE_COMPARISON.md](SMW_ULTIMATE_COMPARISON.md)** | Exemplo de métodos avançados | Referência técnica |

**Contribua**: Pull Requests são bem-vindos!

---

## 📂 ESTRUTURA COMPLETA DOS DOCUMENTOS

### 📘 Documentação Principal

| Arquivo | Tipo | Audiência | Prioridade |
|---------|------|-----------|------------|
| **README.md** | Visão Geral | Todos | 🔴 Alta |
| **GUIA_VISUAL_RAPIDO.md** | Tutorial Visual | Iniciantes | 🔴 Alta |
| **FAQ_CLIENTES.md** | Perguntas & Respostas | Todos | 🔴 Alta |
| **MANUAL_JOGOS_PC.md** | Manual Técnico | Usuários PC | 🟠 Média (se PC) |
| **INDICE_DOCUMENTACAO.md** | Este arquivo | Todos | 🟢 Baixa |

### 📗 Documentação Técnica

| Arquivo | Conteúdo | Quando Consultar |
|---------|----------|------------------|
| **SMW_ULTIMATE_COMPARISON.md** | Relatório técnico de extração avançada | Ao trabalhar com ROMs complexas |
| **SMW_EXTRACTION_REPORT.md** | Métodos de extração testados | Referência de técnicas |

### 📙 Scripts e Ferramentas

| Arquivo | Função | Como Usar |
|---------|--------|-----------|
| **converter_zdoom_simples.py** | Converte tradução para formato ZDoom/GZDoom | `python converter_zdoom_simples.py` |
| **create_zdoom_translation.py** | Conversor avançado ZDoom (auto-busca) | Automático |
| **ultimate_extractor.py** | Extrator híbrido avançado | Para ROMs complexas |
| **final_quality_filter.py** | Filtro de qualidade rigoroso | Pós-tradução |

### 📕 Outros Documentos

| Arquivo | Descrição |
|---------|-----------|
| **requirements.txt** | Dependências Python |
| **INICIAR_AQUI.bat** | Lançador Windows |
| **MANUAL_USO.pdf** | Manual completo (versão anterior) |

---

## 🗺️ FLUXO DE LEITURA RECOMENDADO

### Para Usuários Iniciantes (ROMs):

```
1. README.md (5 min)
   ↓
2. Abrir interface
   ↓
3. Seguir 3 abas (Extração → Tradução → Reinserção)
   ↓
4. FAQ_CLIENTES.md (se tiver dúvidas)
   ↓
✅ PRONTO!
```

**Tempo total**: 10-30 minutos

---

### Para Usuários Iniciantes (Jogos PC):

```
1. README.md (5 min)
   ↓
2. GUIA_VISUAL_RAPIDO.md (3 min)
   ↓
3. MANUAL_JOGOS_PC.md (20 min - LEIA TODO!)
   ↓
4. Identificar tipo de jogo (seção específica)
   ↓
5. Seguir processo: Aba 1 → Aba 2 → Conversor
   ↓
6. FAQ_CLIENTES.md (se tiver problemas)
   ↓
✅ PRONTO!
```

**Tempo total**: 40-60 minutos

---

### Para Profissionais/Comercial:

```
1. README.md (5 min)
   ↓
2. FAQ_CLIENTES.md (15 min - COMPLETO)
   ↓
3. MANUAL_JOGOS_PC.md (20 min - seção de preços)
   ↓
4. GUIA_VISUAL_RAPIDO.md (imprimir para clientes)
   ↓
5. Licença Comercial (consultar termos)
   ↓
✅ Pronto para oferecer serviço!
```

**Tempo total**: 45 minutos

---

## 🔍 BUSCA RÁPIDA POR TÓPICO

### "Como traduzir [tipo de jogo]?"

| Jogo/Console | Documento | Seção |
|--------------|-----------|-------|
| SNES, NES, GBA (ROMs) | README.md | "Quick Start" |
| Jogos PC em geral | MANUAL_JOGOS_PC.md | Início |
| Doom/ZDoom | MANUAL_JOGOS_PC.md | "1. DOOM" |
| Quake | MANUAL_JOGOS_PC.md | "2. QUAKE" |
| Unity | MANUAL_JOGOS_PC.md | "4. JOGOS UNITY" |
| RPG Maker | MANUAL_JOGOS_PC.md | "5. RPG MAKER" |
| Visual Novels | MANUAL_JOGOS_PC.md | "6. VISUAL NOVELS" |

### "Erro ao traduzir..."

| Erro | Documento | Seção |
|------|-----------|-------|
| "utf-8 codec can't decode" | FAQ_CLIENTES.md | "Problemas Comuns" |
| "Extensão inválida" | GUIA_VISUAL_RAPIDO.md | Comparação ROMs vs PC |
| GPU esquentando | FAQ_CLIENTES.md | "GPU esquenta muito" |
| Textos cortados | FAQ_CLIENTES.md | "Tradução ficou cortada" |
| Textos em inglês | FAQ_CLIENTES.md | "Alguns textos em inglês" |

### "Quanto custa..."

| Pergunta | Documento | Seção |
|----------|-----------|-------|
| Framework é grátis? | FAQ_CLIENTES.md | "Preços e Licença" |
| Preciso pagar IA? | FAQ_CLIENTES.md | "Preciso pagar pela tradução?" |
| Preços sugeridos para clientes | MANUAL_JOGOS_PC.md | "Preços Sugeridos" |
| Licença comercial | FAQ_CLIENTES.md | "Posso vender traduções?" |

### "Como instalar/configurar..."

| Tópico | Documento | Seção |
|--------|-----------|-------|
| Instalação do framework | README.md | "Installation" |
| Configurar IA offline (Ollama) | FAQ_CLIENTES.md | "Quais IAs vocês usam?" |
| Configurar IA online (Gemini) | README.md | "Quick Start" |
| Reduzir uso de GPU | FAQ_CLIENTES.md | "GPU esquenta muito" |

---

## 📊 MATRIZ DE DECISÃO

Use esta tabela para decidir qual documento ler:

| Seu Objetivo | Seu Nível | Documento Recomendado |
|--------------|-----------|----------------------|
| Traduzir ROM pela 1ª vez | Iniciante | README.md → Interface (3 abas) |
| Traduzir jogo PC pela 1ª vez | Iniciante | GUIA_VISUAL → MANUAL_JOGOS_PC |
| Entender diferença ROM/PC | Qualquer | GUIA_VISUAL_RAPIDO.md |
| Resolver erro específico | Qualquer | FAQ_CLIENTES.md |
| Oferecer serviço comercial | Intermediário | FAQ_CLIENTES + MANUAL_JOGOS_PC |
| Criar conversor novo | Avançado | MANUAL_JOGOS_PC + código-fonte |
| Referência técnica | Avançado | SMW_ULTIMATE_COMPARISON.md |

---

## 💡 DICAS DE NAVEGAÇÃO

### ✅ Leia na ordem sugerida
Não pule etapas! Cada documento assume conhecimento dos anteriores.

### ✅ Use Ctrl+F para buscar
Todos os documentos são extensos. Use busca interna do navegador/editor.

### ✅ Marque favoritos
Salve os documentos mais usados (FAQ, MANUAL_JOGOS_PC) para acesso rápido.

### ✅ Imprima se preferir
GUIA_VISUAL_RAPIDO e FAQ são ótimos impressos para referência rápida.

### ✅ Mantenha atualizado
Verifique atualizações no GitHub regularmente.

---

## 📞 AINDA TEM DÚVIDAS?

### Depois de ler a documentação:

1. **Procurou no FAQ_CLIENTES.md?**
   → 90% das dúvidas estão lá

2. **Leu o MANUAL_JOGOS_PC.md completo?**
   → Necessário para jogos de PC

3. **Consultou o GitHub Issues?**
   → Outros podem ter tido o mesmo problema

4. **Entre em contato:**
   - GitHub Issues (bugs/sugestões)
   - Email: seu-email@exemplo.com
   - Discord: [Em breve]

---

## 🔄 ATUALIZAÇÕES DA DOCUMENTAÇÃO

| Data | Documento | Mudança |
|------|-----------|---------|
| Dez 2024 | MANUAL_JOGOS_PC.md | ✅ Criado (suporte PC games) |
| Dez 2024 | FAQ_CLIENTES.md | ✅ Criado (perguntas frequentes) |
| Dez 2024 | GUIA_VISUAL_RAPIDO.md | ✅ Criado (tutorial visual) |
| Dez 2024 | SMW_ULTIMATE_COMPARISON.md | ✅ Relatório técnico SMW |
| Dez 2024 | converter_zdoom_simples.py | ✅ Conversor ZDoom |

**Próximas atualizações**:
- Conversor Quake (em desenvolvimento)
- Conversor RPG Maker (planejado)
- Interface web (planejado 2025)

---

## ✅ CHECKLIST DE LEITURA

Marque o que você já leu:

### Documentação Essencial (todos devem ler):
```
[ ] README.md
[ ] GUIA_VISUAL_RAPIDO.md (se trabalha com PC)
[ ] FAQ_CLIENTES.md (ao menos parcialmente)
```

### Documentação Específica (conforme necessidade):
```
[ ] MANUAL_JOGOS_PC.md (se traduz jogos PC)
[ ] SMW_ULTIMATE_COMPARISON.md (se trabalha com ROMs complexas)
[ ] Código-fonte (se é desenvolvedor)
```

### Ferramentas (usar conforme necessário):
```
[ ] converter_zdoom_simples.py (jogos ZDoom)
[ ] ultimate_extractor.py (extração avançada)
[ ] final_quality_filter.py (filtragem de qualidade)
```

---

**Versão do índice**: 1.0
**Última atualização**: Dezembro 2024
**Framework**: ROM Translation Framework v5

📚 **Boa leitura e boas traduções!** 📚
