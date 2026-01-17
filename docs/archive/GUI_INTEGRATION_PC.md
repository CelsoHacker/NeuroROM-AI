# 🖥️ INTEGRAÇÃO GUI - Sistema de Tradução de PC Games

## 🎯 OBJETIVO

Integrar os novos módulos de tradução de PC Games (`core/pc_*.py`) com a interface gráfica existente (`interface_tradutor_final.py`) **SEM refatorar** o código existente.

---

## 📋 PASSOS DE INTEGRAÇÃO

### **1. Adicionar Modo PC Games na GUI**

No arquivo `interface_tradutor_final.py`, adicione um **modo de seleção**:

```python
# Adicione no __init__ ou setup_ui
def criar_modo_selecao(self):
    """Cria seletor ROM vs PC Game."""
    modo_frame = ttk.LabelFrame(self.root, text="Modo de Tradução", padding=10)
    modo_frame.pack(fill=tk.X, padx=10, pady=5)

    self.modo_var = tk.StringVar(value="rom")

    ttk.Radiobutton(
        modo_frame,
        text="🎮 ROM (SNES/NES/GBA/etc)",
        variable=self.modo_var,
        value="rom",
        command=self.atualizar_interface_modo
    ).pack(side=tk.LEFT, padx=10)

    ttk.Radiobutton(
        modo_frame,
        text="💻 PC Game (JSON/XML/INI/etc)",
        variable=self.modo_var,
        value="pc",
        command=self.atualizar_interface_modo
    ).pack(side=tk.LEFT, padx=10)

def atualizar_interface_modo(self):
    """Atualiza labels e tooltips baseado no modo."""
    modo = self.modo_var.get()

    if modo == "rom":
        self.label_arquivo.config(text="Arquivo ROM:")
        self.btn_selecionar.config(text="Selecionar ROM")
    else:
        self.label_arquivo.config(text="Pasta do Jogo:")
        self.btn_selecionar.config(text="Selecionar Pasta")
```

---

### **2. Modificar Seleção de Arquivo**

Altere `selecionar_arquivo()` para suportar pastas:

```python
def selecionar_arquivo(self):
    """Seleciona ROM ou pasta de jogo PC."""
    modo = self.modo_var.get()

    if modo == "rom":
        # Código existente
        arquivo = filedialog.askopenfilename(
            title="Selecione a ROM",
            filetypes=[
                ("ROMs", "*.smc;*.sfc;*.nes;*.gba;*.gb;*.gbc"),
                ("Todos", "*.*")
            ]
        )
    else:
        # Novo: seleção de pasta
        arquivo = filedialog.askdirectory(
            title="Selecione a pasta do jogo PC"
        )

    if arquivo:
        self.caminho_arquivo.set(arquivo)
        self.atualizar_status(f"Selecionado: {os.path.basename(arquivo)}")
```

---

### **3. Criar Função de Extração PC**

Adicione novo método para extração PC (NÃO modifique extração ROM):

```python
def extrair_textos_pc(self):
    """Extrai textos de jogo PC."""
    from core.pc_text_extractor import PCTextExtractor

    game_path = self.caminho_arquivo.get()

    if not game_path:
        messagebox.showerror("Erro", "Selecione a pasta do jogo primeiro")
        return

    try:
        self.atualizar_status("🔍 Extraindo textos do jogo PC...")
        self.atualizar_progresso(10)

        # Extração
        extractor = PCTextExtractor(game_path)
        extractor.extract_all(min_priority=30)

        self.textos_extraidos = extractor.get_translatable_texts()

        self.atualizar_progresso(50)

        if len(self.textos_extraidos) == 0:
            messagebox.showwarning(
                "Aviso",
                "Nenhum texto traduzível encontrado!\n\n"
                "Verifique se a pasta contém arquivos de texto (JSON, XML, INI, etc)"
            )
            return

        # Exporta JSON
        output_json = os.path.join(game_path, "extracted_texts_pc.json")
        extractor.export_to_json(output_json)

        self.atualizar_status(
            f"✅ {len(self.textos_extraidos)} textos extraídos com sucesso!"
        )

        messagebox.showinfo(
            "Sucesso",
            f"Textos extraídos: {len(self.textos_extraidos)}\n\n"
            f"Arquivo salvo em:\n{output_json}"
        )

        self.atualizar_progresso(100)

    except Exception as e:
        messagebox.showerror("Erro", f"Falha na extração:\n{str(e)}")
        self.atualizar_status("❌ Erro na extração")
        self.atualizar_progresso(0)
```

---

### **4. Criar Função de Tradução PC**

Adicione método de tradução PC (reutiliza Gemini API):

```python
def traduzir_jogo_pc(self):
    """Traduz jogo PC completo."""
    from core.pc_pipeline import PCTranslationPipeline

    game_path = self.caminho_arquivo.get()
    api_key = self.api_key.get()

    if not game_path or not api_key:
        messagebox.showerror("Erro", "Preencha caminho do jogo e API key")
        return

    # Confirmação
    resposta = messagebox.askyesno(
        "Confirmar Tradução",
        f"Traduzir jogo em:\n{game_path}\n\n"
        "Isso irá modificar os arquivos do jogo!\n"
        "Backups serão criados automaticamente.\n\n"
        "Deseja continuar?"
    )

    if not resposta:
        return

    try:
        self.atualizar_status("🚀 Iniciando tradução automática...")
        self.atualizar_progresso(0)

        # Pipeline completo
        pipeline = PCTranslationPipeline(game_path)

        # Extração
        self.atualizar_status("[1/3] 📄 Extraindo textos...")
        extraction_result = pipeline.extract_texts(min_priority=30)
        self.atualizar_progresso(30)

        if extraction_result['translatable_count'] == 0:
            messagebox.showwarning("Aviso", "Nenhum texto traduzível encontrado!")
            return

        # Tradução
        self.atualizar_status(
            f"[2/3] 🌐 Traduzindo {extraction_result['translatable_count']} textos..."
        )
        translation_result = pipeline.translate_texts(
            api_key=api_key,
            target_language="Portuguese (Brazil)",
            batch_size=50
        )
        self.atualizar_progresso(70)

        if not translation_result['success']:
            raise Exception(translation_result.get('error', 'Tradução falhou'))

        # Reinserção
        self.atualizar_status("[3/3] 💾 Reinserindo traduções...")
        reinsertion_result = pipeline.reinsert_translations(
            translations=translation_result['translations'],
            create_backup=True
        )
        self.atualizar_progresso(100)

        if not reinsertion_result['success']:
            raise Exception(reinsertion_result.get('error', 'Reinserção falhou'))

        # Sucesso
        messagebox.showinfo(
            "Tradução Concluída",
            f"✅ Jogo traduzido com sucesso!\n\n"
            f"Textos traduzidos: {translation_result['translated_count']}\n"
            f"Arquivos modificados: {reinsertion_result['files_succeeded']}\n\n"
            f"Backups criados em:\n{game_path}"
        )

        self.atualizar_status("✅ Tradução concluída com sucesso!")

    except Exception as e:
        messagebox.showerror("Erro", f"Falha na tradução:\n{str(e)}")
        self.atualizar_status("❌ Erro na tradução")
        self.atualizar_progresso(0)
```

---

### **5. Modificar Botão Principal**

Altere o botão de tradução para chamar função correta:

```python
def iniciar_traducao(self):
    """Inicia tradução baseado no modo selecionado."""
    modo = self.modo_var.get()

    if modo == "rom":
        # Chama função existente
        self.traduzir_rom()  # ou qualquer nome que você use
    else:
        # Chama nova função PC
        self.traduzir_jogo_pc()
```

---

### **6. Adicionar Menu de Opções PC**

Crie menu extra para configurações PC:

```python
def criar_menu_pc(self):
    """Menu de opções para jogos PC."""
    menu_frame = ttk.LabelFrame(self.root, text="Opções PC Games", padding=10)
    menu_frame.pack(fill=tk.X, padx=10, pady=5)

    # Prioridade mínima
    ttk.Label(menu_frame, text="Prioridade Mínima:").grid(row=0, column=0, sticky=tk.W)

    self.pc_priority = tk.IntVar(value=30)
    ttk.Spinbox(
        menu_frame,
        from_=0,
        to=100,
        textvariable=self.pc_priority,
        width=10
    ).grid(row=0, column=1, padx=5)

    ttk.Label(
        menu_frame,
        text="(80=apenas localização, 30=todos textos)",
        font=('Arial', 8)
    ).grid(row=0, column=2, sticky=tk.W)

    # Criar backups
    self.pc_backup = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        menu_frame,
        text="Criar backups antes de modificar",
        variable=self.pc_backup
    ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

    # Botão de extração apenas
    ttk.Button(
        menu_frame,
        text="📄 Apenas Extrair (sem traduzir)",
        command=self.extrair_textos_pc
    ).grid(row=2, column=0, columnspan=3, pady=5)
```

---

## 🎨 LAYOUT SUGERIDO

```
┌─────────────────────────────────────────┐
│  ROM Translation Framework v5.0         │
├─────────────────────────────────────────┤
│  Modo de Tradução:                      │
│  ○ ROM (SNES/NES/GBA)  ● PC Game        │
├─────────────────────────────────────────┤
│  Pasta do Jogo:                         │
│  [C:\Games\MyGame        ] [Selecionar] │
├─────────────────────────────────────────┤
│  API Key Gemini:                        │
│  [AIza...                              ] │
├─────────────────────────────────────────┤
│  Opções PC Games:                       │
│  Prioridade: [30] (30=todos textos)     │
│  ☑ Criar backups antes de modificar     │
│  [📄 Apenas Extrair]                    │
├─────────────────────────────────────────┤
│  [🚀 TRADUZIR JOGO COMPLETO]            │
├─────────────────────────────────────────┤
│  Progresso: ████████░░░░ 80%            │
│  Status: [2/3] Traduzindo textos...     │
└─────────────────────────────────────────┘
```

---

## 📝 EXEMPLO COMPLETO DE INTEGRAÇÃO

### **Código Mínimo para Adicionar à GUI Existente**

```python
# No arquivo interface_tradutor_final.py

# 1. Importe no topo
from core.pc_pipeline import PCTranslationPipeline

# 2. Adicione variável de modo no __init__
self.modo_var = tk.StringVar(value="rom")

# 3. Adicione botão de seleção de modo
self.criar_modo_selecao()

# 4. Adicione nova função
def traduzir_jogo_pc(self):
    """Traduz PC game."""
    pipeline = PCTranslationPipeline(self.caminho_arquivo.get())

    result = pipeline.run_full_pipeline(
        api_key=self.api_key.get(),
        target_language="Portuguese (Brazil)",
        min_priority=30,
        create_backup=True
    )

    if result['success']:
        messagebox.showinfo("Sucesso", "Jogo traduzido!")
    else:
        messagebox.showerror("Erro", result.get('error'))

# 5. Modifique botão de tradução
def iniciar_traducao(self):
    if self.modo_var.get() == "rom":
        self.traduzir_rom()  # Função existente
    else:
        self.traduzir_jogo_pc()  # Nova função
```

---

## ✅ CHECKLIST DE INTEGRAÇÃO

- [ ] Adicionar `modo_var` (ROM vs PC)
- [ ] Modificar seleção de arquivo (suportar pasta)
- [ ] Criar `traduzir_jogo_pc()`
- [ ] Criar `extrair_textos_pc()`
- [ ] Modificar botão principal para chamar função correta
- [ ] Adicionar opções PC (prioridade, backup)
- [ ] Testar com jogo dummy
- [ ] Testar com jogo real (Darkness Within)

---

## 🧪 TESTES SUGERIDOS

### **Teste 1: Extração Apenas**

1. Selecione modo "PC Game"
2. Escolha pasta `dummy_pc_game`
3. Clique "Apenas Extrair"
4. Verifique `dummy_pc_game/extracted_texts_pc.json`
5. ✅ Deve ter ~60 textos

### **Teste 2: Tradução Completa**

1. Selecione modo "PC Game"
2. Escolha pasta `dummy_pc_game`
3. Insira API Key Gemini
4. Clique "TRADUZIR JOGO COMPLETO"
5. Aguarde 30-60 segundos
6. ✅ `localization/english.json` deve estar em português
7. ✅ Backup criado: `english.json.backup_...`

### **Teste 3: Validação de Segurança**

1. Traduza `dummy_pc_game`
2. Abra `localization/english.json`
3. ✅ JSON deve ser válido (sem erros de sintaxe)
4. ✅ Encoding UTF-8 preservado
5. ✅ Estrutura hierárquica mantida

---

## 🐛 TROUBLESHOOTING

### **Erro**: `ModuleNotFoundError: No module named 'core.pc_pipeline'`

**Solução**: Execute GUI a partir da raiz do projeto:
```bash
cd "PROJETO_V5_OFICIAL/rom-translation-framework"
python interface_tradutor_final.py
```

### **Erro**: `FileNotFoundError` ao selecionar pasta

**Solução**: Use `askdirectory()` em vez de `askopenfilename()`:
```python
arquivo = filedialog.askdirectory(title="Selecione a pasta")
```

### **Erro**: Progresso trava em 70%

**Solução**: Tradução está aguardando API. Adicione timeout:
```python
translation_result = pipeline.translate_texts(
    api_key=api_key,
    target_language="Portuguese (Brazil)",
    batch_size=50  # Reduza se travar
)
```

---

## 📚 REFERÊNCIAS

- `docs/PC_GAMES_IMPLEMENTATION.md` - Documentação completa dos módulos
- `core/pc_pipeline.py` - Código do pipeline
- `test_encoding_detector.py` - Testes de encoding

---

**Lembre-se**: NÃO modifique o sistema de ROMs existente. O código PC é totalmente separado e pode coexistir com o sistema ROM sem conflitos.
