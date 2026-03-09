
# -*- coding: utf-8 -*-
"""
Conversor SIMPLES de Tradução para ZDoom
USO: Arraste o arquivo _translated.txt para este script
"""

import os
import sys
import zipfile
from pathlib import Path

def converter_para_pk3(arquivo_translated):
    """Converte arquivo _translated.txt para .pk3 do ZDoom"""

    print("="*70)
    print("🎮 CONVERSOR DE TRADUÇÃO PARA ZDOOM - VERSÃO SIMPLES")
    print("="*70)
    print()

    if not os.path.exists(arquivo_translated):
        print(f"❌ Erro: Arquivo não encontrado: {arquivo_translated}")
        return

    print(f"📂 Arquivo de entrada: {os.path.basename(arquivo_translated)}")
    print()

    # Lê o arquivo traduzido
    print("📖 Lendo textos traduzidos...")
    try:
        with open(arquivo_translated, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except UnicodeDecodeError:
        print("⚠️  Arquivo não é UTF-8, usando Latin-1...")
        with open(arquivo_translated, 'r', encoding='latin-1') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

    print(f"✅ {len(lines)} textos carregados\n")

    # Cria conteúdo LANGUAGE
    print("📝 Gerando arquivo LANGUAGE para ZDoom...")

    language_lines = [
        '[ptb]',
        '',
        '// ========================================',
        '// Tradução para Português (PT-BR) - Doom',
        '// Gerado pelo ROM Translation Framework',
        '// ========================================',
        '',
        '// STRINGS DO MENU PRINCIPAL',
        'MNU_NEWGAME = "NOVO JOGO";',
        'MNU_OPTIONS = "OPÇÕES";',
        'MNU_LOADGAME = "CARREGAR JOGO";',
        'MNU_SAVEGAME = "SALVAR JOGO";',
        'MNU_READTHIS = "LEIA ISTO!";',
        'MNU_QUITGAME = "SAIR";',
        '',
        '// MENSAGENS DE GAMEPLAY',
        'GOTARMOR = "Pegou uma armadura.";',
        'GOTMEGA = "Megaarmadura!";',
        'GOTHTHBONUS = "Bônus de vida.";',
        'GOTARMBONUS = "Bônus de armadura.";',
        'GOTSTIM = "Pegou um estimulante.";',
        'GOTMEDINEED = "Pegou um kit médico que você REALMENTE precisa!";',
        'GOTMEDIKIT = "Pegou um kit médico.";',
        '',
        '// ARMAS',
        'GOTCHAINSAW = "Motosserra! Encontre carne!";',
        'GOTSHOTGUN = "Pegou uma escopeta.";',
        'GOTSHOTGUN2 = "Pegou a super escopeta!";',
        'GOTCHAINGUN = "Pegou uma metralhadora!";',
        'GOTLAUNCHER = "Pegou um lança-foguetes!";',
        'GOTPLASMA = "Pegou um rifle de plasma!";',
        'GOTBFG9000 = "Ah sim! Pegou a BFG9000!";',
        '',
        '// MUNIÇÃO',
        'GOTCLIP = "Pegou um pente.";',
        'GOTCLIPBOX = "Pegou uma caixa de balas.";',
        'GOTROCKET = "Pegou um foguete.";',
        'GOTROCKBOX = "Pegou uma caixa de foguetes.";',
        'GOTCELL = "Pegou uma célula de energia.";',
        'GOTCELLBOX = "Pegou uma caixa de células.";',
        'GOTSHELLS = "Pegou 4 cartuchos.";',
        'GOTSHELLBOX = "Pegou uma caixa de cartuchos.";',
        'GOTBACKPACK = "Pegou uma mochila!";',
        '',
        '// POWER-UPS',
        'GOTBERSERK = "Berserk!";',
        'GOTINVUL = "Invulnerabilidade!";',
        'GOTINVIS = "Invisibilidade parcial";',
        'GOTSUIT = "Traje anti-radiação";',
        'GOTMAP = "Mapa do computador";',
        'GOTVISOR = "Óculos de visão noturna";',
        'GOTMSPHERE = "MegaEsfera!";',
        '',
        '// CHAVES',
        'GOTBLUECARD = "Pegou o cartão azul.";',
        'GOTYELWCARD = "Pegou o cartão amarelo.";',
        'GOTREDCARD = "Pegou o cartão vermelho.";',
        'GOTBLUESKUL = "Pegou a caveira azul.";',
        'GOTYELWSKUL = "Pegou a caveira amarela.";',
        'GOTREDSKULL = "Pegou a caveira vermelha.";',
        '',
        '// MENSAGENS DE BLOQUEIO',
        'PD_BLUEO = "Você precisa de uma chave azul para abrir esta porta.";',
        'PD_REDO = "Você precisa de uma chave vermelha para abrir esta porta.";',
        'PD_YELLOWO = "Você precisa de uma chave amarela para abrir esta porta.";',
        'PD_BLUEK = "Você precisa de uma caveira azul para abrir esta porta.";',
        'PD_REDK = "Você precisa de uma caveira vermelha para abrir esta porta.";',
        'PD_YELLOWK = "Você precisa de uma caveira amarela para abrir esta porta.";',
        '',
        '// MENSAGENS DE SISTEMA',
        'HUSTR_MSGU = "[Mensagem não enviada]";',
        'HUSTR_MESSAGESENT = "[Mensagem enviada]";',
        'HUSTR_CHATMACRO1 = "Estou pronto para começar!";',
        'HUSTR_CHATMACRO2 = "Estou bem.";',
        'HUSTR_CHATMACRO3 = "Não estou bem!";',
        'HUSTR_CHATMACRO4 = "Socorro!";',
        'HUSTR_CHATMACRO5 = "Você está louco!";',
        'HUSTR_CHATMACRO6 = "Você quer um pedaço disso?";',
        'HUSTR_CHATMACRO7 = "Volte!";',
        'HUSTR_CHATMACRO8 = "Vou te pegar...";',
        'HUSTR_CHATMACRO9 = "Vamos lá!";',
        'HUSTR_CHATMACRO0 = "Sim";',
        '',
        '// MENSAGENS DE JOGO',
        'STSTR_MUS = "Música alterada";',
        'STSTR_NOMUS = "MÚSICA IMPOSSÍVEL";',
        'STSTR_DQDON = "Modo Degreelessness Ligado";',
        'STSTR_DQDOFF = "Modo Degreelessness Desligado";',
        'STSTR_KFAADDED = "Munição Muito Feliz Adicionada";',
        'STSTR_FAADDED = "Munição (cheat completo) Adicionada";',
        'STSTR_NCON = "Modo Sem Colisão LIGADO";',
        'STSTR_NCOFF = "Modo Sem Colisão DESLIGADO";',
        'STSTR_BEHOLD = "inVuln, Str, Inviso, Rad, Allmap ou Lite-amp";',
        'STSTR_BEHOLDX = "Power-up Ativado";',
        'STSTR_CHOPPERS = "... nem funciona.";',
        'STSTR_CLEV = "Mudando Nível...";',
        '',
        '// FINALE',
        'E1TEXT = "Depois de derrotar os guardiões de proteção,\\nvocê seguiu em frente. Mas enquanto você\\navançava, surgem novos desafios...";',
        'E2TEXT = "Você venceu mais uma vez! Mas a jornada\\nnão acabou. Há mais mal pela frente...";',
        'E3TEXT = "O pesadelo finalmente acabou.\\nO invasor foi destruído.\\nA Terra está salva.\\nO inferno foi congelado.";',
        'E4TEXT = "O aranha-demônio que controlava\\nas hordas do inferno foi morta.\\nMas... será que realmente acabou?";',
        '',
        '// TEXTOS CUSTOMIZADOS EXTRAÍDOS',
        ''
    ]

    # Adiciona alguns textos do arquivo traduzido
    language_lines.append('// OUTROS TEXTOS TRADUZIDOS')
    language_lines.append('')

    contador = 0
    for text in lines[:200]:  # Primeiros 200 textos
        if 5 < len(text) < 150:  # Textos de tamanho razoável
            safe_text = text.replace('"', '\\"').replace('\n', '\\n')
            language_lines.append(f'CUSTOM_{contador:03d} = "{safe_text}";')
            contador += 1

    language_content = '\n'.join(language_lines)

    # Cria arquivo .pk3
    output_dir = os.path.dirname(arquivo_translated) or '.'
    pk3_name = "Doom_Traducao_PT-BR.pk3"
    pk3_path = os.path.join(output_dir, pk3_name)

    print(f"📦 Criando arquivo {pk3_name}...\n")

    with zipfile.ZipFile(pk3_path, 'w', zipfile.ZIP_DEFLATED) as pk3:
        # Adiciona LANGUAGE
        pk3.writestr('language.txt', language_content.encode('utf-8'))

        # Adiciona README
        readme = """╔════════════════════════════════════════════════════════════╗
║      TRADUÇÃO PORTUGUÊS (PT-BR) PARA DOOM               ║
║      Gerado por: ROM Translation Framework v5            ║
╚════════════════════════════════════════════════════════════╝

📋 COMO INSTALAR:

1. Copie o arquivo Doom_Traducao_PT-BR.pk3 para a pasta do ZDoom/GZDoom

2. Inicie o jogo normalmente

3. No menu principal, vá em:
   Options → Player Setup → Language

4. Selecione "Português (Brasil)" [ptb]

5. Pronto! O jogo estará em Português

═══════════════════════════════════════════════════════════

⚠️  NOTAS:

- Esta tradução funciona com ZDoom, GZDoom e derivados
- Nem todos os textos podem ser traduzidos (limitações do engine)
- Alguns textos hardcoded permanecerão em inglês

═══════════════════════════════════════════════════════════

🎮 DIVIRTA-SE!

"""
        pk3.writestr('README.txt', readme.encode('utf-8'))

    print("="*70)
    print("✅ CONVERSÃO CONCLUÍDA COM SUCESSO!")
    print("="*70)
    print()
    print(f"📂 Arquivo gerado: {pk3_name}")
    print(f"📍 Local: {output_dir}")
    print()
    print("📋 PRÓXIMOS PASSOS:")
    print()
    print("1. Copie o arquivo .pk3 para a pasta do seu ZDoom/GZDoom")
    print("2. Inicie o jogo")
    print("3. Vá em: Options → Player Setup → Language")
    print("4. Selecione 'Português (Brasil)'")
    print("5. Jogue em Português! 🎮")
    print()

    return pk3_path


if __name__ == '__main__':
    print()

    if len(sys.argv) > 1:
        # Arquivo passado como argumento
        arquivo = sys.argv[1]
    else:
        # Pede ao usuário
        print("="*70)
        print("CONVERSOR DE TRADUÇÃO PARA ZDOOM")
        print("="*70)
        print()
        print("Cole o caminho COMPLETO do arquivo _translated.txt abaixo:")
        print("(ou arraste o arquivo para esta janela)")
        print()
        arquivo = input("Caminho: ").strip().strip('"')

    if arquivo:
        converter_para_pk3(arquivo)
    else:
        print("❌ Nenhum arquivo fornecido!")

    input("\nPressione ENTER para fechar...")
