import os
from PyQt6.QtWidgets import QFileDialog

def iniciar_busca_automatica(caminho_inicial):
    # Extensões que seu sistema já aceita para consoles
    extensoes_console = ('.smc', '.sfc', '.bin', '.nes', '.z64', '.n64', '.gba', '.gb', '.gbc', '.nds', '.iso')

    # 1. Se for arquivo de console, retorna direto
    if caminho_inicial.lower().endswith(extensoes_console):
        return caminho_inicial, "console"

    # 2. Se for uma pasta ou executável de PC, varre em busca de textos
    pasta_jogo = os.path.dirname(caminho_inicial)
    prioridades = ['translation', 'lang', 'english', 'localizable', 'texts']

    for root, dirs, files in os.walk(pasta_jogo):
        for file in files:
            # Busca automática do arquivo de texto
            if any(p in file.lower() for p in prioridades) and file.endswith(('.json', '.txt', '.xml')):
                return os.path.join(root, file), "pc_texto"

            # Busca automática de gráficos (OCR simples por nome)
            if file.lower().endswith(('.png', '.dds')) and 'ui' in file.lower():
                return os.path.join(root, file), "pc_grafico"

    return caminho_inicial, "desconhecido"