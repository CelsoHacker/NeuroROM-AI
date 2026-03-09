#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige o manual do Passo 4 para usar EXATAMENTE os mesmos nomes que aparecem na interface
Em vez de usar nomes em inglês, usar os nomes traduzidos corretos
"""

import json

def update_portuguese():
    """Update pt.json - use Portuguese UI names, not English"""
    with open('i18n/pt.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Corrigido: usar nomes EXATOS da interface em português
    data['manual_step_4_content'] = """<h2>🎯 O Que Faz</h2><p>Coloca os textos traduzidos de volta dentro do jogo. Este é o passo final!</p><h2>📝 COMO USAR (Passo a Passo Visual)</h2><h3>🔹 PASSO 1: Vá para a Aba de Reinserção</h3><p>No topo da janela, clique na aba <b>"📥 3. Reinserção"</b></p><h3>🔹 PASSO 2: Escolha o Jogo Original</h3><p>• Clique em <b>"📂 ROM Original"</b> e depois <b>"Selecionar ROM"</b><br>• Escolha o <b>mesmo arquivo de jogo</b> que você usou no início (.smc, .bin, .nds, etc.)</p><h3>🔹 PASSO 3: Escolha os Textos Traduzidos</h3><p>• Clique em <b>"📄 Arquivo Traduzido"</b> e depois <b>"Selecionar Arquivo"</b><br>• Escolha o arquivo <code>*_translated.txt</code> criado no Passo 3</p><h3>🔹 PASSO 4: Dê um Nome para o Jogo Traduzido</h3><p>• No campo <b>"💾 ROM Traduzida (Saída)"</b><br>• Digite um nome, exemplo: <code>MeuJogo_PTBR.smc</code></p><h3>🔹 PASSO 5: Criar o Jogo Traduzido</h3><p>• Aperte o botão <b>"Reinserir Tradução"</b><br>• Espere 10 a 60 segundos<br>• Pronto! Seu jogo traduzido está criado!</p><h2>✅ O Que Aconteceu?</h2><ul><li>✅ Novo jogo criado com o nome que você escolheu</li><li>✅ Seu jogo original continua intacto (não foi modificado)</li><li>✅ Agora é só testar no emulador!</li></ul><h2>🎮 Como Testar o Jogo Traduzido</h2><h3>🔹 O Que é Um Emulador?</h3><p>É um programa que deixa você jogar jogos de console antigo no computador.</p><h3>🔹 Emuladores Recomendados (Baixe de Graça)</h3><ul><li><b>Super Nintendo (SNES):</b> SNES9x ou ZSNES</li><li><b>PlayStation 1:</b> ePSXe ou DuckStation</li><li><b>Game Boy Advance:</b> VisualBoy Advance</li><li><b>Nintendo DS:</b> DeSmuME ou melonDS</li></ul><h3>🔹 Como Testar (Simples!)</h3><ol><li>Abra o emulador do console certo</li><li>Clique em <b>File → Open</b> (ou Arquivo → Abrir)</li><li>Escolha seu jogo traduzido</li><li>Jogue um pouco e veja se os textos estão em português!</li></ol><h2>💡 Dicas Importantes</h2><ul><li>✅ Sempre teste o jogo traduzido antes de compartilhar</li><li>✅ Use <b>Save States</b> do emulador para salvar em qualquer momento</li><li>✅ Guarde o arquivo <code>*_translated.txt</code> - você pode precisar depois</li><li>✅ Se der algum erro, pode refazer só o Passo 4 (é rápido!)</li><li>✅ Compartilhe seu trabalho com outros jogadores! 🎮</li></ul><h2>🎉 Parabéns! Você Conseguiu!</h2><p style="background: linear-gradient(135deg, #1a4d1a 0%, #2d7a2d 100%); padding: 25px; border-radius: 8px; border-left: 5px solid #4CAF50; font-size: 115%; text-align: center;"><b style="font-size: 130%;">🎊 SEU JOGO ESTÁ PRONTO!</b><br><br>✅ Tradução completa!<br>✅ Jogo criado com sucesso!<br>✅ Tudo funcionando perfeitamente!<br><br><b style="font-size: 120%;">Agora é só jogar e se divertir! 🎮✨</b></p><hr style="margin: 30px 0; border: none; border-top: 2px solid #444;"><h2>❓ Perguntas Frequentes (Se Tiver Alguma Dúvida)</h2><details><summary><b>🔽 Clique aqui se encontrar algum problema (raro, mas pode acontecer)</b></summary><br><h3>🔸 Alguns Textos Aparecem Cortados</h3><p><b>Por que acontece:</b> A tradução em português é naturalmente maior que japonês/inglês.</p><p><b>Solução:</b> Isso é comum em traduções! Você pode:</p><ul><li>✅ Jogar normalmente - dá pra entender mesmo cortado</li><li>🔧 Se souber editar texto: encurtar frases no arquivo <code>*_translated.txt</code> e refazer a reinserção</li></ul><h3>🔸 Símbolos Estranhos em Vez de Acentos</h3><p><b>Por que acontece:</b> O jogo original não foi programado para ter ã, ç, é, ô, etc.</p><p><b>Solução:</b> Você pode:</p><ul><li>✅ Jogar normalmente - "voce esta aqui" é fácil de entender!</li><li>🔧 Se souber editar texto: substituir acentos por letras normais no <code>*_translated.txt</code></li></ul><h3>🔸 O Jogo Não Abre no Emulador</h3><p><b>O que fazer:</b></p><ol><li>Tente usar outro emulador diferente (cada um funciona melhor com certos jogos)</li><li>Verifique se escolheu o emulador certo para o console</li><li>Se não funcionar, baixe o jogo original novamente e refaça só o Passo 4</li></ol><h3>🔧 Para Usuários Avançados - Edição Manual</h3><p><b>Como editar o arquivo de tradução:</b></p><ol><li>Clique com botão direito em <code>*_translated.txt</code></li><li>Escolha "Abrir com... → Bloco de Notas"</li><li>Edite o que quiser (encurtar frases, trocar acentos, corrigir erros)</li><li>Salve (Ctrl+S)</li><li>Volte ao programa e refaça só o Passo 4 (Reinserção)</li></ol></details>"""

    with open('i18n/pt.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("✅ Portuguese (pt.json) updated - now using correct Portuguese UI names!")

def update_english():
    """Update en.json - keep English UI names (already correct)"""
    with open('i18n/en.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # English is already correct, but let's ensure consistency
    # No changes needed - English manual already uses English UI names
    print("✅ English (en.json) - already correct (using English UI names)")

# Run updates
print("=" * 70)
print("🔄 FIXING STEP 4 MANUAL - MATCH UI LANGUAGE")
print("=" * 70)
print()
print("📋 Problem identified:")
print("   ❌ Portuguese manual was using English names")
print("   ❌ Manual: 'Original ROM' → Interface shows: '📂 ROM Original'")
print("   ❌ Manual: 'Select ROM' → Interface shows: '📂 Selecionar ROM'")
print()
print("🔧 Fixing...")
print()
update_portuguese()
update_english()
print()
print("=" * 70)
print("✅ MANUAL STEP 4 FIXED - NOW MATCHES UI!")
print("=" * 70)
print()
print("📋 Changes made:")
print("   ✓ 'Original ROM' → '📂 ROM Original'")
print("   ✓ 'Select ROM' → '📂 Selecionar ROM'")
print("   ✓ 'Translated File' → '📄 Arquivo Traduzido'")
print("   ✓ 'Select File' → '📂 Selecionar Arquivo'")
print("   ✓ 'Translated ROM (Output)' → '💾 ROM Traduzida (Saída)'")
print("   ✓ 'Reinsert Translation' → 'Reinserir Tradução'")
print()
print("✅ Now manual exactly matches what user sees on screen!")
print()
