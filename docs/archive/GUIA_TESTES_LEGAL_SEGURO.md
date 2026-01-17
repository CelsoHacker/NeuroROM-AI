# 🧪 GUIA DE TESTES - Versão Legalmente Segura

## ⚖️ AVISO LEGAL OBRIGATÓRIO

**Este guia é para testar com:**
- ✅ ROMs de backup pessoal de jogos que você possui fisicamente
- ✅ Homebrews e jogos de domínio público
- ✅ ROMs de teste criadas por você
- ✅ Demos oficiais liberadas pelos desenvolvedores

**NÃO teste com:**
- ❌ ROMs pirateadas ou baixadas ilegalmente
- ❌ Jogos que você não possui legalmente
- ❌ Conteúdo com copyright sem autorização

---

## 🎯 ESTRATÉGIA DE TESTES REVISADA

### **NÍVEL 1: ROMs Simples (Começar Aqui)**

**Critérios de Seleção:**
- ✅ ROMs pequenas (< 1MB)
- ✅ Encoding ASCII padrão
- ✅ Estrutura linear simples
- ✅ Texto não comprimido

**Exemplos Genéricos:**
1. **Seu backup de jogo de plataforma 2D** (16-bit, ~500KB)
2. **Seu backup de jogo de corrida** (16-bit, ~4MB)
3. **Seu backup de RPG/aventura** (16-bit, ~1MB)

**O Que Validar:**
```
[ ] Extração de texto funciona?
[ ] Textos são legíveis (não lixo binário)?
[ ] Arquivo .txt é criado corretamente?
[ ] Quantidade razoável de strings (> 20)?
[ ] Sem crashes ou erros críticos?
```

---

### **NÍVEL 2: ROMs Médias (Depois do Básico Funcionar)**

**Características:**
- ✅ ROMs maiores (1-4MB)
- ✅ Mais texto/diálogos
- ✅ Possível uso de table files
- ✅ Estruturas um pouco mais complexas

**Progressão de Testes:**
1. Backup de jogo simples → Sucesso? ✅
2. Backup de jogo médio → Sucesso? ✅  
3. Backup de jogo com texto → Sucesso? ✅

---

### **NÍVEL 3: ROMs Complexas (Quando Virar Expert)**

**Características:**
- ⚠️ Compressão customizada
- ⚠️ DTE (Dual Tile Encoding)
- ⚠️ Ponteiros dinâmicos
- ⚠️ Encoding proprietário

**Só Teste Quando:**
- ✅ Níveis 1 e 2 funcionam 100%
- ✅ Você entende a estrutura da ROM
- ✅ Tem tempo para debugging profundo

---

## 📊 MATRIZ DE COMPATIBILIDADE

### **Plataforma SNES - Níveis de Dificuldade**

| Nível | Tipo de Jogo | Complexidade | Tempo Estimado |
|-------|--------------|--------------|----------------|
| 🟢 **Fácil** | Plataforma 2D, Corrida | Baixa | 5-10 min |
| 🟡 **Médio** | Ação, Aventura | Média | 15-30 min |
| 🔴 **Difícil** | RPG japonês, Estratégia | Alta | 1-3 horas |
| ⚫ **Expert** | Jogos com compressão customizada | Muito Alta | 8+ horas |

---

## 🧪 PROTOCOLO DE TESTE GENÉRICO

### **Teste #1: Validação Básica**

```bash
# 1. Preparar ambiente
cd /mnt/project
cp /mnt/user-data/outputs/generic_snes_extractor.py .

# 2. Executar extração com seu backup
python3 generic_snes_extractor.py your_game_backup.smc

# 3. Validar resultado
ls -lh *_extracted_texts.txt
cat *_extracted_texts.txt | head -30

# 4. Critérios de sucesso:
# ✅ Arquivo foi criado?
# ✅ Contém texto legível?
# ✅ Mínimo 20 strings extraídas?
# ✅ Não é só lixo binário?
```

**Se PASSOU**: Continue para Teste #2  
**Se FALHOU**: Debug e ajuste configuração

---

### **Teste #2: Validação de Volume**

```bash
# Repetir com outro backup (diferente do primeiro)
python3 generic_snes_extractor.py another_backup.smc

# Comparar resultados
wc -l *_extracted_texts.txt

# Validar:
# ✅ Segundo arquivo também foi criado?
# ✅ Sistema não travou?
# ✅ Performance aceitável (< 2 min)?
```

---

### **Teste #3: Validação de Robustez**

```bash
# Testar com ROM maior (seu backup de jogo com muito texto)
python3 generic_snes_extractor.py large_backup.smc

# Validar:
# ✅ Processa ROMs grandes (> 2MB)?
# ✅ Não fica sem memória?
# ✅ Textos longos (diálogos) são preservados?
```

---

## 🎯 CHECKLIST DE VALIDAÇÃO

### **Extração Funcional:**
```
[ ] Script executa sem Python errors
[ ] Arquivo _extracted_texts.txt é criado
[ ] Arquivo contém header com metadados
[ ] Textos incluem offsets [0xXXXX]
[ ] Strings são legíveis (não gibberish)
[ ] Mínimo de 20-30 strings extraídas
[ ] Duplicatas foram removidas
[ ] Sem strings < 3 caracteres
```

### **Qualidade dos Dados:**
```
[ ] Textos fazem sentido (palavras reais)
[ ] Pouco lixo binário (< 10%)
[ ] Formatação preservada (espaços, pontuação)
[ ] Números e símbolos estão corretos
[ ] Textos de menu/UI foram capturados
[ ] Diálogos longos não foram cortados
```

---

## 📝 TEMPLATE DE RELATÓRIO DE TESTE

### **Para Cada ROM Testada:**

```markdown
## Teste #X: [Tipo de Jogo Genérico]

**ROM Info:**
- Nome: game_backup_X.smc
- Tamanho: X.XX MB
- Plataforma: SNES
- Encoding esperado: ASCII

**Resultado da Extração:**
- Arquivo gerado: ✅ Sim / ❌ Não
- Tempo de execução: XX segundos
- Strings extraídas: XXX
- Qualidade: 🟢 Ótima / 🟡 Boa / 🔴 Ruim

**Exemplos de Texto Extraído:**
1. [0x12345] "Example text 1"
2. [0x67890] "Example text 2"
3. [0xABCDE] "Example text 3"

**Problemas Encontrados:**
- [ ] Nenhum
- [ ] Lixo binário excessivo
- [ ] Textos cortados
- [ ] Encoding incorreto
- [ ] Outro: _______________

**Próximos Passos:**
- [ ] Testar tradução destes textos
- [ ] Otimizar dados extraídos
- [ ] Ajustar configuração de encoding
```

---

## 🔄 WORKFLOW DE VALIDAÇÃO COMPLETO

```
FASE 1: Extração
├─ Executar generic_snes_extractor.py
├─ Validar arquivo .txt criado
└─ Revisar qualidade dos textos

FASE 2: Otimização (Opcional)
├─ Remover duplicatas
├─ Filtrar lixo binário
└─ Limpar formatação

FASE 3: Tradução
├─ Usar Gemini ou Ollama
├─ Validar tradução mantém sentido
└─ Verificar encoding de saída

FASE 4: Validação Final
├─ Textos traduzidos fazem sentido?
├─ Formatação preservada?
└─ Pronto para reinserção na ROM
```

---

## 🚨 RED FLAGS (Problemas Graves)

### **Se Você Vê Isso, PARE e Debug:**

❌ **Nenhum texto extraído** (0 strings)
→ Problema: Encoding errado ou ROM comprimida
→ Solução: Ajustar configuração ou usar ferramenta específica

❌ **99% lixo binário** (gibberish)
→ Problema: Scanning área errada da ROM
→ Solução: Ajustar offsets de início/fim

❌ **Crash/Erro de memória**
→ Problema: ROM muito grande ou corrupta
→ Solução: Processar em chunks menores

❌ **Textos cortados no meio**
→ Problema: String terminator incorreto
→ Solução: Ajustar detecção de fim de string

---

## 💡 DICAS PRO

### **Para Melhorar Taxa de Sucesso:**

1. **Comece Simples**
   - Teste primeiro com jogos de plataforma/ação
   - Depois vá para RPGs/aventuras
   - Por último, jogos com compressão

2. **Documente Tudo**
   - Anote qual ROM funcionou bem
   - Registre configurações usadas
   - Crie biblioteca de configs por tipo de jogo

3. **Use Ferramentas Auxiliares**
   - Hex editor para verificar estrutura
   - Table file se encoding for customizado
   - ROM detective para auto-detecção

4. **Valide Manualmente**
   - Não confie cegamente no extrator
   - Revise primeiras 50-100 strings
   - Compare com texto real do jogo

---

## 📊 MÉTRICAS DE SUCESSO

### **Sistema Está Pronto Para Lançar Quando:**

```
✅ 90%+ das ROMs simples extraem corretamente
✅ 70%+ das ROMs médias extraem corretamente
✅ 50%+ das ROMs complexas extraem parcialmente
✅ 0 crashes em ROMs válidas
✅ Tempo de extração < 2 minutos para ROMs < 4MB
✅ Menos de 20% de lixo binário em extrações
```

---

## 🎯 PLANO DE AÇÃO REVISADO

### **DIA 1: Validação Básica**
```
[ ] Testar 3 ROMs simples (seus backups pessoais)
[ ] Verificar que extração funciona
[ ] Documentar taxa de sucesso
[ ] Identificar padrões de falha
```

### **DIA 2: Validação Avançada**
```
[ ] Testar 2-3 ROMs de plataforma diferente (PS1)
[ ] Validar encoding Shift-JIS
[ ] Comparar performance SNES vs PS1
[ ] Ajustar configurações conforme necessário
```

### **DIA 3-7: Polimento e Lançamento**
```
[ ] Corrigir bugs encontrados
[ ] Otimizar performance
[ ] Preparar documentação
[ ] Lançar versão beta
```

---

## 📞 COMANDOS SEGUROS (Genéricos)

```bash
# Teste rápido de extração
python3 generic_snes_extractor.py game_backup.smc

# Ver primeiras 30 linhas
head -30 game_backup_extracted_texts.txt

# Contar total de strings
grep -c "^\[0x" game_backup_extracted_texts.txt

# Buscar por palavra específica
grep -i "menu\|start\|game" game_backup_extracted_texts.txt
```

---

**IMPORTANTE**: Este guia foi revisado para estar **100% em conformidade legal**. Nenhuma menção a jogos comerciais específicos, apenas termos genéricos seguros para documentação pública. ✅🔒
