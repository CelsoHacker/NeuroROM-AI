#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor de Tradução para ZDoom/GZDoom
Converte arquivo _translated.txt para formato LANGUAGE do ZDoom
Gera um arquivo .pk3 pronto para usar
"""

import os
import zipfile
from pathlib import Path

class ZDoomTranslationConverter:
    """Converte tradução para formato ZDoom LANGUAGE"""

    def __init__(self, translated_file: str, output_dir: str = None):
        self.translated_file = translated_file
        self.output_dir = output_dir or os.path.dirname(translated_file)

    def read_translated_texts(self) -> list:
        """Lê o arquivo traduzido"""
        print(f"📂 Lendo arquivo: {self.translated_file}")

        # Tenta UTF-8, se falhar usa Latin-1
        try:
            with open(self.translated_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
        except UnicodeDecodeError:
            print("⚠️ Arquivo não é UTF-8, usando Latin-1...")
            with open(self.translated_file, 'r', encoding='latin-1') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

        print(f"✅ {len(lines)} textos carregados")
        return lines

    def create_language_lump(self, texts: list) -> str:
        """Cria o conteúdo do arquivo LANGUAGE no formato ZDoom"""

        language_content = []

        # Cabeçalho do LANGUAGE
        language_content.append('[ptb]')  # Código de idioma Português Brasil
        language_content.append('')
        language_content.append('// Tradução para Português (PT-BR)')
        language_content.append('// Gerado automaticamente pelo ROM Translation Framework')
        language_content.append('')

        # Mapeamento de strings conhecidas do Doom
        # Formato: NOME_DA_STRING = "Texto traduzido"
        doom_strings = {
            # Menu principal
            'DOOM': 'DOOM',
            'NEW GAME': 'NOVO JOGO',
            'OPTIONS': 'OPÇÕES',
            'LOAD GAME': 'CARREGAR JOGO',
            'SAVE GAME': 'SALVAR JOGO',
            'READ THIS!': 'LEIA ISTO!',
            'QUIT GAME': 'SAIR DO JOGO',

            # Mensagens de gameplay
            'PRESS USE': 'PRESSIONE USAR',
            'PRESS SPACE': 'PRESSIONE ESPAÇO',
            'YOU GOT': 'VOCÊ PEGOU',
            'PICKED UP': 'PEGOU',
            'YOU NEED': 'VOCÊ PRECISA',

            # Armas
            'CHAINSAW': 'MOTOSSERRA',
            'SHOTGUN': 'ESCOPETA',
            'SUPER SHOTGUN': 'SUPER ESCOPETA',
            'CHAINGUN': 'METRALHADORA',
            'ROCKET LAUNCHER': 'LANÇA-FOGUETES',
            'PLASMA RIFLE': 'RIFLE DE PLASMA',
            'BFG9000': 'BFG9000',

            # Itens
            'HEALTH': 'VIDA',
            'ARMOR': 'ARMADURA',
            'AMMO': 'MUNIÇÃO',
            'KEY': 'CHAVE',
            'BLUE KEY': 'CHAVE AZUL',
            'RED KEY': 'CHAVE VERMELHA',
            'YELLOW KEY': 'CHAVE AMARELA',

            # Powerups
            'INVULNERABILITY': 'INVULNERABILIDADE',
            'BERSERK': 'BERSERK',
            'INVISIBILITY': 'INVISIBILIDADE',
            'RADIATION SUIT': 'TRAJE ANTI-RADIAÇÃO',
            'COMPUTER MAP': 'MAPA DO COMPUTADOR',
            'LIGHT AMPLIFICATION': 'AMPLIFICADOR DE LUZ',

            # Mensagens de sistema
            'LEVEL COMPLETE': 'NÍVEL COMPLETO',
            'SECRET FOUND': 'SEGREDO ENCONTRADO',
            'YOU ARE DEAD': 'VOCÊ MORREU',
            'GAME SAVED': 'JOGO SALVO',
            'GAME LOADED': 'JOGO CARREGADO',
        }

        # Adiciona strings conhecidas traduzidas
        for eng, ptbr in doom_strings.items():
            # Procura no arquivo traduzido
            found = False
            for text in texts:
                if eng.upper() in text.upper() or ptbr.upper() in text.upper():
                    language_content.append(f'{eng.upper().replace(" ", "_")} = "{ptbr}";')
                    found = True
                    break

            if not found:
                # Usa tradução padrão se não encontrou no arquivo
                language_content.append(f'{eng.upper().replace(" ", "_")} = "{ptbr}";')

        language_content.append('')
        language_content.append('// Textos customizados do arquivo traduzido')
        language_content.append('')

        # Adiciona todos os textos traduzidos como strings genéricas
        for i, text in enumerate(texts[:100]):  # Limita a 100 primeiros textos
            if len(text) > 3 and len(text) < 200:  # Ignora muito curtos ou longos
                safe_text = text.replace('"', '\\"')  # Escapa aspas
                language_content.append(f'CUSTOM_STRING_{i:03d} = "{safe_text}";')

        return '\n'.join(language_content)

    def create_pk3(self, language_content: str) -> str:
        """Cria arquivo .pk3 (ZIP) com o LANGUAGE lump"""

        # Nome do arquivo .pk3
        pk3_name = "Traducao_PT-BR_Doom.pk3"
        pk3_path = os.path.join(self.output_dir, pk3_name)

        print(f"📦 Criando arquivo {pk3_name}...")

        # Cria arquivo ZIP (pk3 é só um ZIP renomeado)
        with zipfile.ZipFile(pk3_path, 'w', zipfile.ZIP_DEFLATED) as pk3:
            # Adiciona arquivo LANGUAGE
            pk3.writestr('language.txt', language_content.encode('utf-8'))

            # Adiciona arquivo de informação
            info = """# Tradução para Português (PT-BR) - Doom
# Gerado pelo ROM Translation Framework v5
#
# COMO USAR:
# 1. Copie este arquivo .pk3 para a pasta do ZDoom/GZDoom
# 2. Inicie o jogo
# 3. No menu Options > Language, selecione "Português (Brasil)"
# 4. Divirta-se!
"""
            pk3.writestr('README.txt', info.encode('utf-8'))

        print(f"✅ Arquivo criado: {pk3_path}")
        return pk3_path

    def convert(self) -> str:
        """Executa a conversão completa"""
        print("="*60)
        print("🔧 CONVERSOR DE TRADUÇÃO PARA ZDOOM")
        print("="*60)

        # 1. Lê textos traduzidos
        texts = self.read_translated_texts()

        # 2. Cria LANGUAGE lump
        print("\n📝 Gerando arquivo LANGUAGE...")
        language_content = self.create_language_lump(texts)

        # 3. Cria arquivo .pk3
        print("\n📦 Empacotando em .pk3...")
        pk3_path = self.create_pk3(language_content)

        print("\n" + "="*60)
        print("✅ CONVERSÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print(f"\n📂 Arquivo gerado: {pk3_path}")
        print("\n📋 INSTRUÇÕES:")
        print("1. Copie o arquivo .pk3 para a pasta do ZDoom")
        print("2. Inicie o jogo")
        print("3. Vá em Options > Player Setup > Language")
        print("4. Selecione 'Português (Brasil)'")
        print("5. Jogue em Português! 🎮")

        return pk3_path


def main():
    """Função principal"""
    import sys

    print("🎮 CONVERSOR DE TRADUÇÃO PARA ZDOOM/GZDOOM")
    print()

    # Procura arquivo _translated.txt na pasta atual
    base_dir = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework"

    # Procura arquivo traduzido
    translated_file = None
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('_translated.txt') and 'zdoom' in file.lower():
                translated_file = os.path.join(root, file)
                break
        if translated_file:
            break

    if not translated_file:
        print("❌ Erro: Arquivo _translated.txt não encontrado!")
        print("Procure manualmente e execute:")
        print("python create_zdoom_translation.py <caminho_do_arquivo_translated.txt>")
        return

    print(f"📂 Arquivo encontrado: {translated_file}")
    print()

    # Executa conversão
    converter = ZDoomTranslationConverter(translated_file)
    pk3_path = converter.convert()

    print(f"\n🎉 Pronto! Arquivo .pk3 gerado em:\n{pk3_path}")


if __name__ == '__main__':
    main()
