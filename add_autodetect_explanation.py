#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adiciona explicação sobre AUTO-DETECTAR no manual do Passo 3
Para que usuários entendam o que significa.
"""

import json

def update_portuguese():
    """Update pt.json with AUTO-DETECT explanation"""
    with open('i18n/pt.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Novo Passo 3 com explicação de AUTO-DETECTAR
    data['manual_step_3_content'] = """<h2>🎯 O Que Faz</h2><p>Traduz o texto do jogo usando Inteligência Artificial (robô tradutor).</p><h2>📝 COMO USAR (Passo a Passo Visual)</h2><h3>🔹 PASSO 1: Vá para a Aba de Tradução</h3><p>No topo da janela, clique na aba <b>"🧠 2. Tradução"</b></p><h3>🔹 PASSO 2: Escolha o Arquivo para Traduzir</h3><p>• Clique no botão <b>"Selecionar Arquivo"</b><br>• Escolha o arquivo <code>*_optimized.txt</code> que você criou no Passo 2</p><h3>🔹 PASSO 2.5: Idioma de Origem (Já Configurado!)</h3><p>Logo abaixo você verá um campo chamado <b>"Idioma de Origem (ROM)"</b> mostrando:</p><p style="background: #2d2d2d; padding: 10px; border-left: 4px solid #4CAF50;"><b>AUTO-DETECTAR</b> ← <span style="color: #4CAF50;">✓ Já vem assim!</span></p><p><b style="color: #4CAF50;">✅ DEIXE EM AUTO-DETECTAR! Não precisa mudar!</b></p><p><b>O que é AUTO-DETECTAR?</b></p><ul><li>🔍 <b>O programa descobre sozinho</b> se o jogo está em inglês, japonês, espanhol, etc.</li><li>✅ <b>Você não precisa saber</b> qual é o idioma do jogo original</li><li>✅ <b>Funciona com qualquer jogo</b> - japonês, inglês, coreano, chinês, etc.</li><li>⚡ <b>É automático</b> - o programa detecta e traduz!</li></ul><p><i>💡 Só mude se você tiver certeza absoluta do idioma original do jogo. Mas deixar em AUTO-DETECTAR é sempre a melhor opção!</i></p><h3>🔹 PASSO 3: Configurar o Modo de Tradução</h3><p>Você verá uma seção chamada <b>"Modo de Tradução"</b> com um menu que mostra:</p><p style="background: #2d2d2d; padding: 10px; border-left: 4px solid #4CAF50;"><b>🔄 Auto (Gemini → Ollama)</b> ← <span style="color: #4CAF50;">✓ Já vem selecionado!</span></p><p><b style="color: #4CAF50;">✅ DEIXE ASSIM! Essa é a melhor opção!</b></p><p>O que significa "Auto (Gemini → Ollama)":</p><ul><li>✅ <b>Começa usando Gemini</b> (rápido, usa internet do Google)</li><li>✅ <b>Quando acabar o grátis, muda sozinho para Ollama</b> (no seu PC, sem limite)</li><li>✅ <b>VOCÊ NÃO PRECISA FAZER NADA! É automático!</b></li></ul><h3>🔹 PASSO 4: Chave do Google (Opcional - Pode pular!)</h3><p>Mais abaixo você verá <b>"API Configuration"</b> com um campo para <b>"API Key:"</b></p><p><b>Pode deixar em branco!</b> O programa vai funcionar sem isso usando Ollama (grátis, ilimitado).</p><p><i>Se quiser usar Gemini (mais rápido), veja como conseguir a chave grátis no fim dessa página.</i></p><h3>🔹 PASSO 5: Iniciar a Tradução</h3><p>• Aperte o botão grande <b>"🤖 Traduzir com IA"</b><br>• Veja a barra de progresso encher<br>• Pode demorar de 15 minutos a 1 hora</p><h2>⏱️ Quanto Tempo Demora?</h2><ul><li><b>Jogos pequenos:</b> 5-15 minutos</li><li><b>Jogos médios:</b> 20-40 minutos</li><li><b>Jogos grandes:</b> 1 hora ou mais</li></ul><p>💡 <b>Pode fechar o programa e continuar depois! O progresso fica salvo.</b></p><h2>✅ MEU PC AGUENTA?</h2><p><b style="font-size: 130%; color: #4CAF50;">✓ SIM! FUNCIONA EM QUALQUER PC!</b></p><h3>🌐 Modo Gemini (internet):</h3><ul><li>✅ Qualquer PC com internet funciona!</li><li>✅ Não precisa de placa de vídeo</li><li>✅ Não precisa de muito RAM</li><li>✅ Até notebook velho funciona!</li></ul><h3>💻 Modo Ollama (no seu PC):</h3><ul><li>✅ Qualquer PC funciona - só muda a velocidade!</li><li>PC Básico (8GB RAM): Mais devagar, mas funciona</li><li>PC Bom (16GB RAM): Rápido</li><li>PC Potente (32GB RAM): Muito rápido</li></ul><h2>💰 Quanto Custa?</h2><ul><li><b>Gemini Grátis:</b> 20 traduções por dia = R$ 0,00</li><li><b>Ollama:</b> Ilimitado = R$ 0,00 (só gasta luz do PC)</li><li><b>Gemini Pago (se quiser):</b> R$ 3 a R$ 12 por jogo completo</li></ul><h2>🔑 EXTRA: Como Conseguir Chave do Google Gemini (Grátis)</h2><p><i>Isso é opcional! O programa funciona sem isso.</i></p><ol><li>Visite: <b>https://aistudio.google.com/apikey</b></li><li>Faça login com sua conta Google</li><li>Clique em "Create API Key"</li><li>Copie a chave</li><li>Cole no campo "API Key:" do programa</li></ol><p>✅ Pronto! Você ganha 20 traduções rápidas grátis por dia!</p><h2>💻 EXTRA: O Que é Ollama e Como Instalar</h2><p>Ollama é um programa GRÁTIS que traduz no seu PC sem internet.</p><ol><li>Baixe em: <b>https://ollama.com</b></li><li>Instale como qualquer programa</li><li>Pronto! O programa vai usar automaticamente</li></ol><p><b>Vantagem:</b> Ilimitado, sem custos, sem limite diário!</p>"""

    with open('i18n/pt.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ Portuguese (pt.json) updated with AUTO-DETECT explanation!")

def update_english():
    """Update en.json with AUTO-DETECT explanation"""
    with open('i18n/en.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # New Step 3 with AUTO-DETECT explanation
    data['manual_step_3_content'] = """<h2>🎯 What It Does</h2><p>Translates game text using Artificial Intelligence (robot translator).</p><h2>📝 HOW TO USE (Step-by-Step Visual Guide)</h2><h3>🔹 STEP 1: Go to Translation Tab</h3><p>At the top of the window, click the <b>"🧠 2. Translation"</b> tab</p><h3>🔹 STEP 2: Choose File to Translate</h3><p>• Click the <b>"Select File"</b> button<br>• Choose the <code>*_optimized.txt</code> file you created in Step 2</p><h3>🔹 STEP 2.5: Source Language (Already Configured!)</h3><p>Right below you'll see a field called <b>"Source Language (ROM)"</b> showing:</p><p style="background: #2d2d2d; padding: 10px; border-left: 4px solid #4CAF50;"><b>AUTO-DETECT</b> ← <span style="color: #4CAF50;">✓ Already set!</span></p><p><b style="color: #4CAF50;">✅ LEAVE IT ON AUTO-DETECT! No need to change!</b></p><p><b>What is AUTO-DETECT?</b></p><ul><li>🔍 <b>The program figures out by itself</b> if the game is in English, Japanese, Spanish, etc.</li><li>✅ <b>You don't need to know</b> what language the original game is in</li><li>✅ <b>Works with any game</b> - Japanese, English, Korean, Chinese, etc.</li><li>⚡ <b>It's automatic</b> - the program detects and translates!</li></ul><p><i>💡 Only change if you're absolutely certain of the original language. But leaving it on AUTO-DETECT is always the best option!</i></p><h3>🔹 STEP 3: Configure Translation Mode</h3><p>You will see a section called <b>"Translation Mode"</b> with a menu showing:</p><p style="background: #2d2d2d; padding: 10px; border-left: 4px solid #4CAF50;"><b>🔄 Auto (Gemini → Ollama)</b> ← <span style="color: #4CAF50;">✓ Already selected!</span></p><p><b style="color: #4CAF50;">✅ LEAVE IT LIKE THIS! This is the best option!</b></p><p>What "Auto (Gemini → Ollama)" means:</p><ul><li>✅ <b>Starts using Gemini</b> (fast, uses Google internet)</li><li>✅ <b>When free runs out, automatically switches to Ollama</b> (on your PC, unlimited)</li><li>✅ <b>YOU DON'T NEED TO DO ANYTHING! It's automatic!</b></li></ul><h3>🔹 STEP 4: Google Key (Optional - Can skip!)</h3><p>Further down you'll see <b>"API Configuration"</b> with a field for <b>"API Key:"</b></p><p><b>Can leave it blank!</b> The program will work without it using Ollama (free, unlimited).</p><p><i>If you want to use Gemini (faster), see how to get free key at the end of this page.</i></p><h3>🔹 STEP 5: Start Translation</h3><p>• Press the big button <b>"🤖 Translate with AI"</b><br>• Watch the progress bar fill up<br>• May take 15 minutes to 1 hour</p><h2>⏱️ How Long Does It Take?</h2><ul><li><b>Small games:</b> 5-15 minutes</li><li><b>Medium games:</b> 20-40 minutes</li><li><b>Large games:</b> 1 hour or more</li></ul><p>💡 <b>Can close program and continue later! Progress is saved.</b></p><h2>✅ WILL MY PC WORK?</h2><p><b style="font-size: 130%; color: #4CAF50;">✓ YES! WORKS ON ANY PC!</b></p><h3>🌐 Gemini Mode (internet):</h3><ul><li>✅ Any PC with internet works!</li><li>✅ No graphics card needed</li><li>✅ No high RAM needed</li><li>✅ Even old laptops work!</li></ul><h3>💻 Ollama Mode (on your PC):</h3><ul><li>✅ Any PC works - only speed changes!</li><li>Basic PC (8GB RAM): Slower, but works</li><li>Good PC (16GB RAM): Fast</li><li>Powerful PC (32GB RAM): Very fast</li></ul><h2>💰 How Much Does It Cost?</h2><ul><li><b>Gemini Free:</b> 20 translations per day = $0.00</li><li><b>Ollama:</b> Unlimited = $0.00 (only uses PC electricity)</li><li><b>Gemini Paid (if you want):</b> $0.50-$2.00 per full game</li></ul><h2>🔑 EXTRA: How to Get Google Gemini Key (Free)</h2><p><i>This is optional! Program works without it.</i></p><ol><li>Visit: <b>https://aistudio.google.com/apikey</b></li><li>Login with your Google account</li><li>Click "Create API Key"</li><li>Copy the key</li><li>Paste in "API Key:" field in program</li></ol><p>✅ Done! You get 20 fast free translations per day!</p><h2>💻 EXTRA: What is Ollama and How to Install</h2><p>Ollama is a FREE program that translates on your PC without internet.</p><ol><li>Download at: <b>https://ollama.com</b></li><li>Install like any program</li><li>Done! Program will use it automatically</li></ol><p><b>Advantage:</b> Unlimited, no cost, no daily limit!</p>"""

    with open('i18n/en.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ English (en.json) updated with AUTO-DETECT explanation!")

# Run updates
print("=" * 70)
print("🔄 ADDING AUTO-DETECT EXPLANATION TO MANUAL STEP 3")
print("=" * 70)
print()
update_portuguese()
update_english()
print()
print("=" * 70)
print("✅ AUTO-DETECT EXPLANATION ADDED!")
print("=" * 70)
print()
print("📋 Changes made:")
print("   ✓ Added PASSO 2.5 explaining 'AUTO-DETECTAR'")
print("   ✓ Explains: program auto-detects Japanese, English, etc.")
print("   ✓ Clear message: 'DEIXE EM AUTO-DETECTAR! Não precisa mudar!'")
print("   ✓ User now understands they don't need to know original language")
print()
