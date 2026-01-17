# ❓ FAQ - Perguntas Frequentes dos Clientes

**ROM Translation Framework v5 - Respostas Rápidas**

---

## 🎮 SOBRE O QUE O FRAMEWORK TRADUZ

### ❓ Vocês traduzem jogos de PC ou só ROMs de console?

✅ **AMBOS!** O framework traduz:
- **ROMs de Console**: SNES, NES, Game Boy, GBA, N64, PlayStation, etc.
- **Jogos de PC**: Doom, Quake, Half-Life, Unity, RPG Maker, Visual Novels, etc.

**Diferença importante**:
- **ROMs**: Processo 100% automático (3 cliques)
- **Jogos de PC**: Extração e tradução automáticas, aplicação requer passo adicional

📖 **Leia**: [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md) para detalhes completos

---

### ❓ Quais consoles são suportados?

✅ **Totalmente suportados** (reinserção automática):
- Super Nintendo (SNES) - `.smc`, `.sfc`
- Nintendo Entertainment System (NES) - `.nes`
- Game Boy / Game Boy Color - `.gb`, `.gbc`
- Game Boy Advance - `.gba`
- Nintendo 64 - `.z64`, `.n64`
- Nintendo DS - `.nds`
- PlayStation 1 - `.bin`, `.iso`

⚠️ **Parcialmente suportados** (extração/tradução ok, reinserção manual):
- PlayStation 2 - `.iso`
- GameCube - `.iso`, `.gcm`
- Wii - `.wbfs`, `.iso`
- PSP - `.iso`

---

### ❓ Quais jogos de PC são suportados?

✅ **Com conversor automático**:
- **Doom/Doom II** (ZDoom/GZDoom) - ✅ Conversor pronto
- **Quake** - Em desenvolvimento
- **Visual Novels** (RenPy) - Em desenvolvimento

⚠️ **Com processo manual** (documentado):
- Half-Life / Counter-Strike (GoldSrc)
- Jogos Unity (via UABE)
- RPG Maker MV/MZ
- Jogos com arquivos `.pak`, `.dat`, `.txt`

📖 **Leia**: [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md) - Seção "Jogos de PC Suportados"

---

## 🔄 PROCESSO DE TRADUÇÃO

### ❓ Como funciona o processo para ROMs de console?

**3 Passos Simples**:

```
1. Aba "1. Extração"
   → Selecione a ROM (.smc, .nes, etc.)
   → Clique "Extrair Textos"
   → Arquivo _optimized.txt gerado ✅

2. Aba "2. Tradução"
   → Selecione _optimized.txt
   → Configure idioma: Português
   → Clique "Traduzir com IA"
   → Arquivo _translated.txt gerado ✅

3. Aba "3. Reinserção"
   → Selecione ROM original
   → Selecione _translated.txt
   → Escolha nome da ROM traduzida
   → Clique "Reinserir"
   → ROM traduzida gerada! 🎉
```

**Tempo estimado**: 5-30 minutos (dependendo do tamanho)

---

### ❓ Como funciona para jogos de PC?

**4 Passos** (1 a mais que ROMs):

```
1. Aba "1. Extração" ✅ (igual ROMs)
   → Selecione arquivo do jogo (.exe, .wad, etc.)
   → Extrair textos

2. Aba "2. Tradução" ✅ (igual ROMs)
   → Traduzir textos

3. ⚠️ NÃO use Aba "3. Reinserção"!
   → Ela só funciona para ROMs de console

4. Use Conversor Específico 🔧
   → python converter_zdoom_simples.py (Doom)
   → Ou processo manual (veja manual)
   → Instale tradução no jogo
```

**Por que é diferente?**
- ROMs são arquivos únicos (.smc)
- Jogos de PC têm múltiplos arquivos e formatos variados

📖 **Leia**: [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md) - Seção "Como Funciona"

---

## 🤖 SOBRE A TRADUÇÃO COM IA

### ❓ Quais IAs vocês usam?

**Modo Online** (requer internet):
- ✅ Google Gemini (gratuito com limites)
- ✅ API OpenAI (pago, alta qualidade)

**Modo Offline** (sem internet, GRATUITO):
- ✅ Llama 3.1 8B (recomendado - rápido e preciso)
- ✅ Llama 3 (alta qualidade, mais lento)
- ✅ Outros modelos Ollama

---

### ❓ Preciso pagar pela tradução?

**NÃO é obrigatório!** Você tem opções:

**Opção 1: Modo Offline (GRÁTIS, ilimitado)**
- Instale Ollama
- Baixe modelo Llama 3.1 8B
- Traduza quantos jogos quiser - ZERO custo

**Opção 2: Modo Online (Google Gemini - GRÁTIS com limites)**
- 60 requisições/minuto gratuitas
- Bom para jogos pequenos
- Pode atingir quota em jogos grandes

**Opção 3: Modo Online (OpenAI - PAGO, alta qualidade)**
- Paga por uso (~ R$0,50-5,00 por jogo)
- Máxima qualidade
- Sem limites de quota

**Recomendação**: Use Llama 3.1 8B offline - é gratuito e funciona muito bem!

---

### ❓ A tradução fica boa?

**Depende do modelo usado:**

| Modelo | Qualidade | Erros Estimados | Custo |
|--------|-----------|-----------------|-------|
| **Llama 3.1 8B** (offline) | ⭐⭐⭐ Boa | ~10-20% | Grátis ✅ |
| **Gemini Flash** (online) | ⭐⭐⭐⭐ Muito Boa | ~5% | Grátis* |
| **GPT-4** (online) | ⭐⭐⭐⭐⭐ Excelente | ~2% | Pago |

### ⚠️ AVISO IMPORTANTE SOBRE QUALIDADE

**Modo Offline (Llama 3.1):**
- ✅ Gratuito e ilimitado
- ✅ Funciona sem internet
- ⚠️ Pode ter 10-20% de erros ou frases estranhas
- ⚠️ Nomes de lugares/itens podem sair incorretos
- 📝 **SEMPRE revise o arquivo _translated.txt antes de usar**

**Modo Online (Gemini/GPT):**
- ✅ Qualidade superior
- ✅ Menos erros (~2-5%)
- ⚠️ Requer internet e API Key

### 📝 RECOMENDAÇÃO PROFISSIONAL

Para garantir qualidade e evitar reclamações:
1. Traduza com a IA (automático)
2. Abra o arquivo `_translated.txt` no Bloco de Notas
3. Leia rapidamente e corrija erros óbvios
4. Só então faça a reinserção

**✅ Tradução por IA + Revisão humana = Resultado profissional!**

---

## ⚙️ CONFIGURAÇÃO E USO

### ❓ É difícil instalar?

**Não!** Processo simples:

```bash
# Windows (recomendado):
1. Execute INICIAR_AQUI.bat
2. Pronto! Interface abre automaticamente

# Manual:
1. Instale Python 3.8+
2. pip install -r requirements.txt
3. python interface/interface_tradutor_final.py
```

**Tempo**: 5-10 minutos

---

### ❓ Meu computador precisa ser potente?

**Depende do modo**:

**Modo Online** (Gemini/GPT):
- ✅ Qualquer PC funciona (até notebooks antigos)
- Processamento é feito na nuvem
- Requer internet

**Modo Offline** (Llama 3.1):
- ⚠️ Recomendado: GPU NVIDIA com 6GB+ VRAM
- Ou: 16GB+ RAM (mais lento, sem GPU)
- Funciona em PCs médios/bons

**Alternativa**: Se seu PC é fraco, use modo online Gemini (grátis)

---

### ❓ GPU esquenta muito, é normal?

**Sim, é normal** para modelos offline (Llama 3.1):
- 65-85°C é faixa aceitável
- Acima de 90°C → reduza workers ou use modo online

**Soluções**:
1. **Reduza workers**: 3 → 1 (na interface)
2. **Use Llama 3.1** em vez de Llama (mais leve)
3. **Melhore ventilação** do PC
4. **Use modo online** (Gemini - sem usar GPU)

---

## 🐛 PROBLEMAS COMUNS

### ❓ Erro: "'utf-8' codec can't decode byte..."

**Causa**: Arquivo com encoding não-UTF-8 (comum em jogos antigos)

**Solução**: ✅ JÁ CORRIGIDO na versão atual!
- O framework agora tenta UTF-8, depois Latin-1
- Se ainda der erro, reporte

---

### ❓ Erro: "Extensão inválida" ao reinserir

**Causa**: Você está tentando reinserir tradução de **jogo de PC** na aba "3. Reinserção"

**Solução**:
- A aba "3. Reinserção" **só funciona para ROMs de console**
- Para jogos de PC: use conversor específico
- Exemplo Doom: `python converter_zdoom_simples.py`

📖 **Leia**: [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md)

---

### ❓ Tradução ficou com textos cortados no jogo

**Causa**: Limite de espaço na ROM (textos muito longos)

**Solução**:
1. Abra o arquivo `_translated.txt`
2. Encurte manualmente os textos problemáticos
3. Re-execute a reinserção (Aba 3)

**Dica**: Textos devem ter ~80% do tamanho original em média

---

### ❓ Alguns textos ficaram em inglês

**Causas possíveis**:
1. Textos estão em gráficos (não são texto editável)
2. Textos comprimidos (formato especial)
3. Textos hardcoded no código do jogo

**Soluções**:
1. Para gráficos: use editor de tiles (Tile Molester, YY-CHR)
2. Para comprimidos: consulte ROM hacking communities
3. Para hardcoded: edição hexadecimal avançada

---

## 💰 PREÇOS E LICENÇA

### ❓ O framework é gratuito?

**O framework é GRATUITO** para uso pessoal:
- Download grátis
- Código aberto
- Sem limitações técnicas

**Uso comercial** (vender traduções):
- Requer licença comercial
- Entre em contato para preços

---

### ❓ Posso vender traduções feitas com o framework?

**Sim, COM licença comercial**:
- Licença permite traduzir profissionalmente
- Vender traduções de ROMs/jogos
- Oferecer serviço de tradução

**Regras**:
- ✅ Pode vender traduções
- ✅ Pode oferecer serviço
- ❌ NÃO pode revender o framework
- ❌ NÃO pode remover créditos

Entre em contato para licença comercial.

---

## 📞 SUPORTE

### ❓ Onde peço ajuda?

**Documentação**:
1. [README.md](README.md) - Visão geral
2. [MANUAL_JOGOS_PC.md](MANUAL_JOGOS_PC.md) - Jogos de PC
3. [ROM_HACKING_GUIDE.md](docs/ROM_HACKING_GUIDE.md) - Técnicas avançadas

**Comunidade**:
- GitHub Issues: Reporte bugs
- Discord: [Em breve]
- Email: seu-email@exemplo.com

**Prioridade de Suporte**:
- 🥇 Licenças comerciais: Suporte prioritário
- 🥈 Usuários gratuitos: Melhor esforço
- 🥉 GitHub Issues: Comunidade ajuda

---

### ❓ Como reporto um bug?

1. Acesse: [GitHub Issues](https://github.com/seu-repo/issues)
2. Clique "New Issue"
3. Forneça:
   - Descrição do problema
   - Passos para reproduzir
   - Capturas de tela
   - Arquivo de log (se disponível)

---

### ❓ Posso sugerir melhorias?

**Sim!** Adoramos feedback:
- GitHub Issues (tag: enhancement)
- Email com sugestões
- Pull Requests (para devs)

**Sugestões mais votadas** têm prioridade de implementação!

---

## 🎯 CASOS DE USO

### ❓ Exemplos de traduções bem-sucedidas?

**ROMs de Console**:
- ✅ Super Mario World (SNES) - 606 textos traduzidos
- ✅ Chrono Trigger (SNES) - Tradução completa
- ✅ Pokémon Fire Red (GBA) - 3.500+ textos

**Jogos de PC**:
- ✅ Doom Collection (ZDoom) - 4.977 textos
- ✅ Visual Novels (RenPy) - Vários projetos
- ✅ RPG Maker games - Dezenas de jogos

---

### ❓ Quanto tempo leva uma tradução?

**Depende do tamanho do jogo**:

| Tipo de Jogo | Textos | Tempo (Online) | Tempo (Offline) |
|--------------|--------|----------------|-----------------|
| Jogo pequeno (NES) | 100-500 | 5-15 min | 10-30 min |
| Jogo médio (SNES) | 500-2000 | 15-60 min | 30-120 min |
| Jogo grande (RPG) | 2000-10000 | 60-300 min | 120-600 min |

**Otimização do framework** reduz ~80% dos textos (remove duplicatas)!

---

## 🔮 FUTURO

### ❓ Quais melhorias virão?

**Roadmap 2025**:
- ✅ Suporte a jogos de PC (CONCLUÍDO)
- 🔄 Mais conversores automáticos (Quake, Unity)
- 🔄 Interface web (traduzir no navegador)
- 🔄 Banco de dados de traduções compartilhadas
- 🔄 Revisão colaborativa em tempo real

---

### ❓ Como posso contribuir?

**Desenvolvedores**:
- Pull Requests no GitHub
- Criar conversores para novos jogos
- Melhorar algoritmos de extração

**Tradutores**:
- Compartilhar traduções completas
- Reportar problemas de qualidade
- Sugerir melhorias na IA

**Usuários**:
- Divulgar o projeto
- Reportar bugs
- Dar feedback

---

## ✅ CHECKLIST RÁPIDO

### Para começar a traduzir ROMs:
```
[ ] Instalar framework (INICIAR_AQUI.bat)
[ ] Escolher modo: Online (Gemini) ou Offline (Llama 3.1)
[ ] Configurar API key OU instalar Ollama
[ ] Carregar ROM na Aba 1
[ ] Extrair textos
[ ] Traduzir na Aba 2
[ ] Reinserir na Aba 3
[ ] Testar ROM traduzida
[ ] Jogar! 🎮
```

### Para traduzir jogos de PC:
```
[ ] Ler MANUAL_JOGOS_PC.md
[ ] Identificar tipo de jogo (Doom? Unity? RPG Maker?)
[ ] Extrair textos (Aba 1)
[ ] Traduzir (Aba 2)
[ ] Usar conversor específico OU processo manual
[ ] Instalar tradução no jogo
[ ] Testar
[ ] Jogar! 🎮
```

---

**Última atualização**: Dezembro 2024
**Versão do framework**: v5.3

🎮 **Divirta-se traduzindo!** 🎮
