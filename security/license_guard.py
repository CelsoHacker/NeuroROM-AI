# -*- coding: utf-8 -*-
import requests
import sys
import os
import json
import hashlib
print(hashlib.sha256("CELSO-123".encode()).hexdigest())                # Biblioteca de Criptografia
IS_DEV = True  # mude para False na versão que vai para o cliente

from PyQt6.QtWidgets import QInputDialog, QMessageBox, QApplication

# Configuração
PRODUCT_PERMALINK = "SEU_LINK_DO_PRODUTO_GUMROAD"
CACHE_FILE = "license.key"

# HASH SHA-256 DA SENHA "CELSO-123"
# Se um hacker ler o código, ele vê isso, mas não sabe qual é a senha original.
DEV_HASH = "aeaca21fc59a6b91bdce8842109fbb1aa3386089667a78e58ab1cc5b06bc8eb9"

def verify_gumroad_license(license_key):
    if IS_DEV:
        input_hash = hashlib.sha256(license_key.encode()).hexdigest()
        if input_hash == DEV_HASH:
            return True, "Modo Desenvolvedor Ativado (Hash Confirmado)!"
    # resto da verificação no Gumroad...

    # ------------------------------

    """
    Verifica se a chave é válida direto no servidor do Gumroad.
    """
    url = "https://api.gumroad.com/v2/licenses/verify"
    payload = {
        "product_permalink": PRODUCT_PERMALINK,
        "license_key": license_key
    }

    try:
        r = requests.post(url, data=payload)
        data = r.json()

        if data.get("success") == True:
            if data["purchase"]["refunded"] or data["purchase"]["chargebacked"]:
                return False, "Esta chave foi reembolsada ou cancelada."
            return True, "Licença Válida."
        else:
            return False, "Chave inválida ou pirata."

    except Exception as e:
        return False, f"Erro de conexão: {e}"

def check_license_gui():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            saved_key = f.read().strip()
            is_valid, msg = verify_gumroad_license(saved_key)
            if is_valid:
                return True

    app = QApplication(sys.argv)

    while True:
        key, ok = QInputDialog.getText(None, "Ativação Necessária",
            "Obrigado por comprar o Tradutor Universal!\n\n"
            "Por favor, digite sua Chave de Licença (enviada por e-mail):\n"
            "Sem a chave, o programa não funciona.")

        if not ok:
            sys.exit()

        if not key:
            continue

        is_valid, msg = verify_gumroad_license(key.strip())

        if is_valid:
            with open(CACHE_FILE, 'w') as f:
                f.write(key.strip())
            QMessageBox.information(None, "Sucesso", f"Software Ativado! {msg}")
            return True
        else:
            QMessageBox.critical(None, "Erro de Ativação", f"{msg}\n\nSe você baixou isso de graça, compre o original.")

if __name__ == "__main__":
    check_license_gui()