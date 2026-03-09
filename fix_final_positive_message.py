#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORREÇÃO 1: Remove menção a problemas da mensagem de parabéns.
CORREÇÃO 2: Move troubleshooting para seção separada (não no fluxo principal).
"""

import json

def update_portuguese():
    """Update pt.json - positive ending, troubleshooting separated"""
    with open('i18n/pt.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Novo Passo 4 - Mensagem positiva, troubleshooting separado
    data['manual_step_4_content'] = """<h2>🎯 O Que Faz</h2><p>Coloca os textos traduzidos de volta dentro do jogo. Este é o passo final!</p><h2>📝 COMO USAR (Passo a Passo Visual)</h2><h3>🔹 PASSO 1: Vá para a Aba de Reinserção</h3><p>No topo da janela, clique na aba <b>"📥 3. Reinserção"</b></p><h3>🔹 PASSO 2: Escolha o Jogo Original</h3><p>• Clique em <b>"📂 Original ROM"</b> e depois <b>"Select ROM"</b><br>• Escolha o <b>mesmo arquivo de jogo</b> que você usou no início (.smc, .bin, .nds, etc.)</p><h3>🔹 PASSO 3: Escolha os Textos Traduzidos</h3><p>• Clique em <b>"📄 Translated File"</b> e depois <b>"Select File"</b><br>• Escolha o arquivo <code>*_translated.txt</code> criado no Passo 3</p><h3>🔹 PASSO 4: Dê um Nome para o Jogo Traduzido</h3><p>• No campo <b>"💾 Translated ROM (Output)"</b><br>• Digite um nome, exemplo: <code>MeuJogo_PTBR.smc</code></p><h3>🔹 PASSO 5: Criar o Jogo Traduzido</h3><p>• Aperte o botão <b>"Reinsert Translation"</b><br>• Espere 10 a 60 segundos<br>• Pronto! Seu jogo traduzido está criado!</p><h2>✅ O Que Aconteceu?</h2><ul><li>✅ Novo jogo criado com o nome que você escolheu</li><li>✅ Seu jogo original continua intacto (não foi modificado)</li><li>✅ Agora é só testar no emulador!</li></ul><h2>🎮 Como Testar o Jogo Traduzido</h2><h3>🔹 O Que é Um Emulador?</h3><p>É um programa que deixa você jogar jogos de console antigo no computador.</p><h3>🔹 Emuladores Recomendados (Baixe de Graça)</h3><ul><li><b>Super Nintendo (SNES):</b> SNES9x ou ZSNES</li><li><b>PlayStation 1:</b> ePSXe ou DuckStation</li><li><b>Game Boy Advance:</b> VisualBoy Advance</li><li><b>Nintendo DS:</b> DeSmuME ou melonDS</li></ul><h3>🔹 Como Testar (Simples!)</h3><ol><li>Abra o emulador do console certo</li><li>Clique em <b>File → Open</b> (ou Arquivo → Abrir)</li><li>Escolha seu jogo traduzido</li><li>Jogue um pouco e veja se os textos estão em português!</li></ol><h2>💡 Dicas Importantes</h2><ul><li>✅ Sempre teste o jogo traduzido antes de compartilhar</li><li>✅ Use <b>Save States</b> do emulador para salvar em qualquer momento</li><li>✅ Guarde o arquivo <code>*_translated.txt</code> - você pode precisar depois</li><li>✅ Se der algum erro, pode refazer só o Passo 4 (é rápido!)</li><li>✅ Compartilhe seu trabalho com outros jogadores! 🎮</li></ul><h2>🎉 Parabéns! Você Conseguiu!</h2><p style="background: linear-gradient(135deg, #1a4d1a 0%, #2d7a2d 100%); padding: 25px; border-radius: 8px; border-left: 5px solid #4CAF50; font-size: 115%; text-align: center;"><b style="font-size: 130%;">🎊 SEU JOGO ESTÁ PRONTO!</b><br><br>✅ Tradução completa!<br>✅ Jogo criado com sucesso!<br>✅ Tudo funcionando perfeitamente!<br><br><b style="font-size: 120%;">Agora é só jogar e se divertir! 🎮✨</b></p><hr style="margin: 30px 0; border: none; border-top: 2px solid #444;"><h2>❓ Perguntas Frequentes (Se Tiver Alguma Dúvida)</h2><details><summary><b>🔽 Clique aqui se encontrar algum problema (raro, mas pode acontecer)</b></summary><br><h3>🔸 Alguns Textos Aparecem Cortados</h3><p><b>Por que acontece:</b> A tradução em português é naturalmente maior que japonês/inglês.</p><p><b>Solução:</b> Isso é comum em traduções! Você pode:</p><ul><li>✅ Jogar normalmente - dá pra entender mesmo cortado</li><li>🔧 Se souber editar texto: encurtar frases no arquivo <code>*_translated.txt</code> e refazer a reinserção</li></ul><h3>🔸 Símbolos Estranhos em Vez de Acentos</h3><p><b>Por que acontece:</b> O jogo original não foi programado para ter ã, ç, é, ô, etc.</p><p><b>Solução:</b> Você pode:</p><ul><li>✅ Jogar normalmente - "voce esta aqui" é fácil de entender!</li><li>🔧 Se souber editar texto: substituir acentos por letras normais no <code>*_translated.txt</code></li></ul><h3>🔸 O Jogo Não Abre no Emulador</h3><p><b>O que fazer:</b></p><ol><li>Tente usar outro emulador diferente (cada um funciona melhor com certos jogos)</li><li>Verifique se escolheu o emulador certo para o console</li><li>Se não funcionar, baixe o jogo original novamente e refaça só o Passo 4</li></ol><h3>🔧 Para Usuários Avançados - Edição Manual</h3><p><b>Como editar o arquivo de tradução:</b></p><ol><li>Clique com botão direito em <code>*_translated.txt</code></li><li>Escolha "Abrir com... → Bloco de Notas"</li><li>Edite o que quiser (encurtar frases, trocar acentos, corrigir erros)</li><li>Salve (Ctrl+S)</li><li>Volte ao programa e refaça só o Passo 4 (Reinserção)</li></ol></details>"""

    # Adicionar strings para o popup de parabéns (internacionalizado)
    data['congratulations_title'] = "🎉 Parabéns!"
    data['congratulations_message'] = "🎊 Você traduziu seu primeiro jogo!\n\n✅ Tradução completa!\n✅ Jogo criado com sucesso!\n✅ Tudo funcionando perfeitamente!\n\nAgora é só jogar e se divertir! 🎮✨"

    with open('i18n/pt.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ Portuguese (pt.json) updated - positive message!")

def update_english():
    """Update en.json - positive ending, troubleshooting separated"""
    with open('i18n/en.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['manual_step_4_content'] = """<h2>🎯 What It Does</h2><p>Puts translated text back inside the game. This is the final step!</p><h2>📝 HOW TO USE (Step-by-Step Visual Guide)</h2><h3>🔹 STEP 1: Go to Reinsertion Tab</h3><p>At the top of the window, click the <b>"📥 3. Reinsertion"</b> tab</p><h3>🔹 STEP 2: Choose Original Game</h3><p>• Click <b>"📂 Original ROM"</b> then <b>"Select ROM"</b><br>• Choose the <b>same game file</b> you used at the beginning (.smc, .bin, .nds, etc.)</p><h3>🔹 STEP 3: Choose Translated Text</h3><p>• Click <b>"📄 Translated File"</b> then <b>"Select File"</b><br>• Choose the <code>*_translated.txt</code> file created in Step 3</p><h3>🔹 STEP 4: Name Your Translated Game</h3><p>• In the <b>"💾 Translated ROM (Output)"</b> field<br>• Type a name, example: <code>MyGame_EN.smc</code></p><h3>🔹 STEP 5: Create Translated Game</h3><p>• Press the <b>"Reinsert Translation"</b> button<br>• Wait 10 to 60 seconds<br>• Done! Your translated game is created!</p><h2>✅ What Happened?</h2><ul><li>✅ New game created with the name you chose</li><li>✅ Your original game stays intact (not modified)</li><li>✅ Now just test it in the emulator!</li></ul><h2>🎮 How to Test Translated Game</h2><h3>🔹 What is An Emulator?</h3><p>It's a program that lets you play old console games on your computer.</p><h3>🔹 Recommended Emulators (Download Free)</h3><ul><li><b>Super Nintendo (SNES):</b> SNES9x or ZSNES</li><li><b>PlayStation 1:</b> ePSXe or DuckStation</li><li><b>Game Boy Advance:</b> VisualBoy Advance</li><li><b>Nintendo DS:</b> DeSmuME or melonDS</li></ul><h3>🔹 How to Test (Simple!)</h3><ol><li>Open the emulator for the correct console</li><li>Click <b>File → Open</b></li><li>Choose your translated game</li><li>Play a bit and see if text is in your language!</li></ol><h2>💡 Important Tips</h2><ul><li>✅ Always test translated game before sharing</li><li>✅ Use emulator <b>Save States</b> to save anytime</li><li>✅ Keep the <code>*_translated.txt</code> file - you may need it later</li><li>✅ If you get an error, you can redo just Step 4 (it's fast!)</li><li>✅ Share your work with other players! 🎮</li></ul><h2>🎉 Congratulations! You Did It!</h2><p style="background: linear-gradient(135deg, #1a4d1a 0%, #2d7a2d 100%); padding: 25px; border-radius: 8px; border-left: 5px solid #4CAF50; font-size: 115%; text-align: center;"><b style="font-size: 130%;">🎊 YOUR GAME IS READY!</b><br><br>✅ Translation complete!<br>✅ Game created successfully!<br>✅ Everything working perfectly!<br><br><b style="font-size: 120%;">Now just play and have fun! 🎮✨</b></p><hr style="margin: 30px 0; border: none; border-top: 2px solid #444;"><h2>❓ Frequently Asked Questions (If You Have Any Doubts)</h2><details><summary><b>🔽 Click here if you encounter any problems (rare, but can happen)</b></summary><br><h3>🔸 Some Text Appears Cut Off</h3><p><b>Why it happens:</b> Translations are naturally longer than Japanese/English.</p><p><b>Solution:</b> This is common in translations! You can:</p><ul><li>✅ Play normally - you can understand even when cut off</li><li>🔧 If you know how to edit text: shorten sentences in <code>*_translated.txt</code> and redo reinsertion</li></ul><h3>🔸 Weird Symbols Instead of Accents</h3><p><b>Why it happens:</b> The original game wasn't programmed for special letters (ã, ñ, é, etc.)</p><p><b>Solution:</b> You can:</p><ul><li>✅ Play normally - "cafe" is easy to understand!</li><li>🔧 If you know how to edit text: replace accents with normal letters in <code>*_translated.txt</code></li></ul><h3>🔸 Game Won't Open in Emulator</h3><p><b>What to do:</b></p><ol><li>Try using a different emulator (each works better with certain games)</li><li>Check if you chose the right emulator for the console</li><li>If it doesn't work, download the original game again and redo only Step 4</li></ol><h3>🔧 For Advanced Users - Manual Editing</h3><p><b>How to edit the translation file:</b></p><ol><li>Right-click <code>*_translated.txt</code></li><li>Choose "Open with... → Notepad"</li><li>Edit whatever you want (shorten sentences, replace accents, fix errors)</li><li>Save (Ctrl+S)</li><li>Go back to the program and redo only Step 4 (Reinsertion)</li></ol></details>"""

    # Add strings for congratulations popup (internationalized)
    data['congratulations_title'] = "🎉 Congratulations!"
    data['congratulations_message'] = "🎊 You translated your first game!\n\n✅ Translation complete!\n✅ Game created successfully!\n✅ Everything working perfectly!\n\nNow just play and have fun! 🎮✨"

    with open('i18n/en.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ English (en.json) updated - positive message!")

# Run updates
print("🔄 Updating with POSITIVE final message...")
print("📋 Removing mention of problems from congratulations")
print("📋 Moving troubleshooting to separate collapsible section")
print()
update_portuguese()
update_english()
print()
print("=" * 70)
print("✅ FINAL MESSAGE UPDATED - NOW POSITIVE!")
print("=" * 70)
print()
print("📋 Changes made:")
print("   ✓ Removed 'even if there are problems' from congratulations")
print("   ✓ Now says: 'Everything working perfectly!'")
print("   ✓ Troubleshooting moved to FAQ section (hidden by default)")
print("   ✓ Added i18n strings: congratulations_title & congratulations_message")
print()
print("⚠️  NEXT STEP: Need to update Python code to use i18n for popup!")
print()
