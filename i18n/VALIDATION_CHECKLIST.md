# ✅ Checklist de Validação i18n - ROM Translation Framework

## Fase 1: Arquitetura Validada

### ✅ Arquivos JSON Criados
- [x] `i18n/pt.json` - Português (Brasil)
- [x] `i18n/en.json` - English
- [x] `i18n/zh.json` - 中文 (Chinês Simplificado)

### ✅ JSON Loader Implementado
- [x] `ProjectConfig.load_translations()` com cache
- [x] Fallback hierárquico: idioma atual → EN → {}
- [x] Método `tr()` refatorado com fallback triplo:
  1. Idioma do usuário
  2. Inglês (EN)
  3. `[KEY_NAME]` (debug visível)

### ✅ Refatorações Completadas
- [x] `manual_combo` usando IDs lógicos (`manual_guide_title`, `manual_step_1-4`)
- [x] `show_manual_step()` carregando de JSON (não mais hardcoded)
- [x] `ROADMAP` usando `tr()` para todas as strings (`roadmap_header`, `roadmap_cat_*`)

---

## Fase 2: Testes de Validação

### 🧪 Teste 1: Troca de Idioma PT → ZH → EN

**Objetivo**: Validar se dropdown e UI atualizam corretamente

**Passos**:
1. Iniciar aplicação em PT (padrão)
2. Ir em Configurações → Idioma da Interface
3. Trocar para "中文 (Chinese)"
4. **Validar**:
   - [ ] Tabs mudam para chinês (提取, 翻译, 重新插入, 设置)
   - [ ] Dropdown "Guia de Uso Profissional" muda para "专业用户指南"
   - [ ] Itens do dropdown mudam para "第1步: 提取", etc.
5. Trocar para "English (US)"
6. **Validar**:
   - [ ] Tabs mudam para inglês (Extraction, Translation, Reinsertion, Settings)
   - [ ] Dropdown muda para "Professional User Guide"

---

### 🧪 Teste 2: Guia de Uso Profissional Multi-idioma

**Objetivo**: Garantir que janelas de ajuda abrem no idioma correto

**Passos (em Português)**:
1. Configurações → Idioma: Português
2. Clicar em dropdown "Guia de Uso Profissional"
3. Selecionar "Passo 1: Extração"
4. **Validar**:
   - [ ] Janela abre com título "📖 Passo 1: Extração de Textos"
   - [ ] Conteúdo HTML em português ("Objetivo", "Instruções Passo a Passo")

**Passos (em Chinês)**:
1. Configurações → Idioma: 中文
2. Clicar em dropdown "专业用户指南"
3. Selecionar "第1步: 提取"
4. **Validar**:
   - [ ] Janela abre com título "📖 第1步: 文本提取"
   - [ ] Conteúdo HTML em chinês ("目标", "逐步说明")

**Passos (em Inglês)**:
1. Configurações → Idioma: English
2. Clicar em dropdown "Professional User Guide"
3. Selecionar "Step 1: Extraction"
4. **Validar**:
   - [ ] Janela abre com título "📖 Step 1: Text Extraction"
   - [ ] Conteúdo HTML em inglês ("Objective", "Step-by-Step Instructions")

---

### 🧪 Teste 3: Roadmap Multi-idioma

**Objetivo**: Validar que roadmap abre com texto correto em cada idioma

**Passos (em Português)**:
1. Configurações → Idioma: Português
2. Extração → Plataforma → Selecionar "📋 Próximos Consoles (Roadmap)..."
3. **Validar**:
   - [ ] Janela abre com título "🗺️ Roadmap"
   - [ ] Header: "Plataformas em Desenvolvimento"
   - [ ] Descrição: "Estas plataformas serão adicionadas em futuras atualizações:"
   - [ ] Categorias: "PlayStation", "Nintendo Classic", "Nintendo Portable", "Sega", "Xbox", "Outros"
   - [ ] Nota: "Nota: As atualizações são gratuitas para compradores do framework."

**Passos (em Chinês)**:
1. Configurações → Idioma: 中文
2. Extração → Plataforma → Selecionar "📋 即将推出的游戏机 (路线图)..."
3. **Validar**:
   - [ ] Header: "开发中的平台"
   - [ ] Descrição: "这些平台将在未来更新中添加:"
   - [ ] Categorias: "PlayStation", "任天堂经典", "任天堂掌机", "世嘉", "Xbox", "其他"
   - [ ] Nota: "注意: 框架购买者可免费获得更新。"

**Passos (em Inglês)**:
1. Configurações → Idioma: English
2. Extraction → Platform → Selecionar "📋 Upcoming Consoles (Roadmap)..."
3. **Validar**:
   - [ ] Header: "Platforms in Development"
   - [ ] Descrição: "These platforms will be added in future updates:"
   - [ ] Categorias traduzidas corretamente
   - [ ] Nota: "Note: Updates are free for framework purchasers."

---

### 🧪 Teste 4: Fallback para EN

**Objetivo**: Testar se idiomas sem tradução completa fazem fallback correto

**Simular idioma incompleto**:
1. Editar `i18n/zh.json`
2. Remover a chave `"manual_step_2_title"`
3. Reiniciar aplicação
4. Configurações → Idioma: 中文
5. Guia de Uso Profissional → Selecionar "第2步: 优化"
6. **Validar**:
   - [ ] Título da janela usa fallback EN: "📖 Step 2: Data Optimization"
   - [ ] Conteúdo permanece em ZH (não foi removido)

---

### 🧪 Teste 5: Debug de Chaves Ausentes

**Objetivo**: Verificar se chaves inexistentes são exibidas como `[KEY_NAME]`

**Passos**:
1. Editar `interface_tradutor_final.py` temporariamente
2. Adicionar `self.tr("chave_inexistente")` em algum label
3. Reiniciar aplicação
4. **Validar**:
   - [ ] Label exibe `[chave_inexistente]` (torna bug visível)

---

### 🧪 Teste 6: Persistência de Idioma

**Objetivo**: Garantir que idioma selecionado é salvo e restaurado

**Passos**:
1. Configurações → Idioma: 中文
2. Fechar aplicação
3. Reabrir aplicação
4. **Validar**:
   - [ ] UI inicia em chinês automaticamente
   - [ ] Dropdown "Idioma da Interface" mostra "中文 (Chinese)" selecionado

---

## Fase 3: Testes de Regressão

### 🔍 Funcionalidades Existentes Não Podem Quebrar

- [ ] Extração de ROM continua funcionando (SNES, PS1, PC)
- [ ] Otimização de dados funciona
- [ ] Tradução com Gemini/Ollama funciona
- [ ] Reinserção na ROM funciona
- [ ] Troca de tema visual funciona
- [ ] API Key é salva/carregada corretamente

---

## Fase 4: Critérios de Aceite Final

### ✅ Sistema i18n Está Pronto Quando:

1. **Escalabilidade**:
   - [ ] Adicionar novo idioma requer apenas criar `i18n/idioma.json`
   - [ ] ZERO alterações no código Python para adicionar idioma

2. **Separação Total**:
   - [ ] Nenhuma string traduzida é usada como identificador lógico
   - [ ] Todas as ações usam IDs internos (`guide_professional`, não texto)

3. **Fallback Previsível**:
   - [ ] Idioma do usuário → EN → `[KEY]` sempre funciona
   - [ ] Nunca exibe chinês quando deveria exibir português

4. **Debug Amigável**:
   - [ ] Chaves faltando aparecem como `[KEY_NAME]` (não quebra a UI)
   - [ ] Fácil identificar strings não traduzidas

---

## 🎯 Status Atual

**Arquitetura**: ✅ Implementada
**Próximo Passo**: Executar testes de validação acima

**Observações**:
- Sistema foi projetado para ser **production-ready**
- Suporta adicionar árabe, russo, klingon sem quebrar nada
- Idiomas são camada visual, lógica independe totalmente
