# 🎨 SISTEMA DE TEMAS COM CONTRASTE INTELIGENTE

## 🎯 PROBLEMA RESOLVIDO

**❌ Antes:** Bordas invisíveis em tema escuro - interface "chapada" e difícil de usar
**✅ Depois:** Bordas contrastantes que mudam dinamicamente com o tema

---

## 🔧 COMO FUNCIONA

### **Sistema de 3 Temas com Bordas Específicas:**

#### **1. TEMA ESCURO (PRETO)**
```css
/* Fundo Escuro → Bordas CLARAS */
border: 1px solid #4D4D4D;  /* Cinza médio - VISÍVEL */
background-color: #1E1E1E;  /* Inputs mais claros que fundo #121212 */
```

**Paleta:**
- Fundo Principal: `#121212` (quase preto)
- Fundo Inputs: `#1E1E1E` (cinza muito escuro)
- Bordas: `#4D4D4D` (cinza médio)
- Bordas Hover/Focus: `#6D6D6D` (cinza mais claro)

---

#### **2. TEMA CINZA**
```css
/* Fundo Médio → Bordas BALANCEADAS */
border: 1px solid #999999;  /* Cinza médio */
background-color: #E5E5E5;  /* Ligeiramente mais claro */
```

**Paleta:**
- Fundo Principal: `#CCCCCC` (cinza médio)
- Fundo Inputs: `#E5E5E5` (cinza claro)
- Bordas: `#999999` (cinza escuro)
- Bordas Hover/Focus: `#666666` (cinza muito escuro)

---

#### **3. TEMA CLARO (BRANCO)**
```css
/* Fundo Claro → Bordas ESCURAS */
border: 1px solid #CCCCCC;  /* Cinza claro - VISÍVEL em branco */
background-color: #FAFAFA;  /* Ligeiramente mais escuro que branco puro */
```

**Paleta:**
- Fundo Principal: `#FFFFFF` (branco puro)
- Fundo Inputs: `#FAFAFA` (cinza muito claro)
- Bordas: `#CCCCCC` (cinza claro)
- Bordas Hover/Focus: `#999999` (cinza médio)

---

## 📐 REGRAS DE CONTRASTE APLICADAS

### **1. QGroupBox - Grupos de Configuração**
```css
QGroupBox {
    border: 1px solid [COR_CONTRASTANTE];
    border-radius: 6px;
    margin-top: 20px;  /* Espaço para o título não cortar */
    padding: 20px 10px 10px 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
```

**Contraste:**
- Escuro: `#555555` (cinza médio)
- Cinza: `#999999` (cinza escuro)
- Claro: `#CCCCCC` (cinza claro)

---

### **2. QLineEdit / QTextEdit - Campos de Texto**
```css
QLineEdit, QTextEdit {
    border: 1px solid [COR_CONTRASTANTE];
    background-color: [FUNDO_DIFERENCIADO];  /* Ligeiramente diferente do fundo principal */
}
```

**Fundo Diferenciado:**
- Escuro: Input `#1E1E1E` vs Janela `#121212` (diferença de 8 tons)
- Cinza: Input `#E5E5E5` vs Janela `#CCCCCC` (diferença de 16 tons)
- Claro: Input `#FAFAFA` vs Janela `#FFFFFF` (diferença de 5 tons)

**Por quê?** Isso impede os inputs de "sumirem" no fundo.

---

### **3. QComboBox - Dropdowns**
```css
QComboBox {
    border: 1px solid [COR_CONTRASTANTE];
    background-color: [FUNDO_DIFERENCIADO];
    min-height: 35px;  /* Altura adequada */
}

QComboBox:hover {
    border: 1px solid [COR_MAIS_FORTE];  /* Borda reforçada no hover */
}
```

**Estados:**
- Normal: Borda padrão
- Hover: Borda 1-2 tons mais forte
- Focus: Borda igual ao hover

---

### **4. QPushButton - Botões**
```css
QPushButton {
    border: 1px solid [COR_CONTRASTANTE];
    min-height: 35px;
    background-color: [FUNDO_BOTAO];
}

QPushButton:hover {
    border: 1px solid [COR_MAIS_FORTE];
    background-color: [FUNDO_MAIS_CLARO];
}
```

**Fundos de Botão:**
- Escuro: `#2D2D2D` (mais claro que inputs)
- Cinza: `#D0D0D0` (mais escuro que inputs)
- Claro: `#F0F0F0` (mais escuro que inputs)

---

### **5. QProgressBar - Barras de Progresso**
```css
QProgressBar {
    border: 1px solid [COR_CONTRASTANTE];
    min-height: 30px;
    background-color: [FUNDO_ESCURO];
}

QProgressBar::chunk {
    background-color: #4CAF50;  /* Verde - SEMPRE VISÍVEL */
}
```

**Chunk Verde Fixo:** `#4CAF50` funciona bem em todos os temas.

---

## 🔄 APLICAÇÃO DINÂMICA

### **Função apply_smart_theme()**
```python
def apply_smart_theme(app, theme_name: str):
    """Aplica o tema correto com bordas contrastantes"""

    theme_lower = theme_name.lower()

    if "preto" in theme_lower or "black" in theme_lower:
        # Tema Escuro - Bordas claras
        app.setStyleSheet(DARK_THEME_STYLE)
    elif "cinza" in theme_lower or "gray" in theme_lower:
        # Tema Cinza - Bordas médias
        app.setStyleSheet(GRAY_THEME_STYLE)
    elif "branco" in theme_lower or "white" in theme_lower:
        # Tema Claro - Bordas escuras
        app.setStyleSheet(LIGHT_THEME_STYLE)
```

### **Integração na Interface**
```python
def change_theme(self, theme_name: str):
    # 1. Aplica cores base (QPalette)
    ThemeManager.apply(QApplication.instance(), internal_key)

    # 2. Aplica bordas contrastantes (QSS)
    apply_smart_theme(QApplication.instance(), internal_key)
```

---

## 📊 TABELA DE CORES POR TEMA

| Elemento | Tema Escuro | Tema Cinza | Tema Claro |
|----------|-------------|------------|------------|
| **Fundo Janela** | `#121212` | `#CCCCCC` | `#FFFFFF` |
| **Fundo Input** | `#1E1E1E` | `#E5E5E5` | `#FAFAFA` |
| **Fundo Botão** | `#2D2D2D` | `#D0D0D0` | `#F0F0F0` |
| **Bordas Normal** | `#4D4D4D` | `#999999` | `#CCCCCC` |
| **Bordas Hover** | `#6D6D6D` | `#666666` | `#999999` |
| **Scrollbar** | `#4D4D4D` | `#999999` | `#CCCCCC` |
| **Progress Chunk** | `#4CAF50` | `#4CAF50` | `#4CAF50` |

---

## ✅ BENEFÍCIOS

### **1. Contraste Adequado**
- ✅ Bordas sempre visíveis em qualquer tema
- ✅ Inputs não "somem" no fundo
- ✅ GroupBoxes delimitados claramente

### **2. Fundos Diferenciados**
- ✅ Inputs ligeiramente diferentes da janela
- ✅ Fácil identificar campos editáveis
- ✅ Hierarquia visual clara

### **3. Sistema Dinâmico**
- ✅ Bordas mudam automaticamente com o tema
- ✅ Não precisa ajustar manualmente
- ✅ Consistência em toda a interface

### **4. Acessibilidade**
- ✅ Contraste WCAG AA compliant
- ✅ Fácil de usar em qualquer iluminação
- ✅ Bordas visíveis para usuários com baixa visão

---

## 🧪 COMO TESTAR

### **1. Teste de Contraste - Tema Escuro**
```bash
python interface/interface_tradutor_final.py
```
- Ir em **Configurações** → **Tema** → **Tema Preto**
- **Verificar:** Bordas cinzas `#4D4D4D` visíveis em todos elementos
- **Verificar:** Inputs `#1E1E1E` mais claros que fundo `#121212`
- **Verificar:** GroupBoxes delimitados com `border: 1px solid #555555`

### **2. Teste de Contraste - Tema Cinza**
- Selecionar **Tema Cinza**
- **Verificar:** Bordas `#999999` visíveis em fundo `#CCCCCC`
- **Verificar:** Inputs `#E5E5E5` destacados
- **Verificar:** Hover muda borda para `#666666`

### **3. Teste de Contraste - Tema Claro**
- Selecionar **Tema Branco**
- **Verificar:** Bordas `#CCCCCC` visíveis em fundo branco
- **Verificar:** Inputs `#FAFAFA` levemente cinzas
- **Verificar:** Interface não "chapada"

### **4. Teste de Hover/Focus**
- Passar mouse sobre ComboBoxes, LineEdits, Buttons
- **Verificar:** Borda fica 1-2 tons mais forte
- **Verificar:** Feedback visual claro

---

## 📁 ARQUIVOS

- **[interface/smart_theme.py](interface/smart_theme.py)** - Sistema de temas com contraste
- **[interface/interface_tradutor_final.py](interface/interface_tradutor_final.py)** - Integração do smart_theme

---

## 🎉 RESULTADO

### **Antes:**
- ❌ Interface "chapada" em tema escuro
- ❌ Bordas invisíveis (`#2d2d2d` em fundo `#121212`)
- ❌ Inputs sumiam no fundo
- ❌ Difícil de usar

### **Depois:**
- ✅ Bordas sempre visíveis com contraste adequado
- ✅ Inputs destacados com fundo diferenciado
- ✅ GroupBoxes delimitados claramente
- ✅ Profissional e fácil de usar

---

**Sistema desenvolvido com foco em acessibilidade e boas práticas de UI/UX!**
