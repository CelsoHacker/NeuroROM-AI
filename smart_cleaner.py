import os
import shutil
import datetime
from pathlib import Path

# ==============================================================================
# SMART CLEANER - ORGANIZADOR INTELIGENTE DE PROJETO
# ==============================================================================

# CONFIGURAÇÃO DE DIRETÓRIOS
BASE_DIR = Path.cwd()
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Pastas de Destino
TRASH_DIR = BASE_DIR / "_LIXEIRA_REVISAR" / TIMESTAMP
ROMS_DIR = BASE_DIR / "_INPUT_ROMS"
CORE_DIR = BASE_DIR / "core"
INTERFACE_DIR = BASE_DIR / "interface"
CONFIG_DIR = BASE_DIR / "config"

# Arquivos INTOCÁVEIS (Ficam na raiz)
KEEP_IN_ROOT = [
    "smart_cleaner.py",         # O próprio script
    "main.py",
    "interface_tradutor_final.py", # Seu arquivo principal atual
    "requirements.txt",
    "README.md",
    ".gitignore",
    "venv",                     # Pasta do ambiente virtual
    ".git"                      # Pasta do git
]

# HEURÍSTICAS DE JULGAMENTO
PATTERNS_LIXO = [
    "_extracted", "_optimized", "_translated", "_reinserted",
    "(copy)", " - Cópia", "_bkp", "_old",
    "v5.0", "v5.1", "v5.2", # Versões antigas
    "Log_", "relatorio_"
]

EXTENSIONS_ROMS = [
    '.smc', '.sfc', '.bin', '.iso', '.nds', '.gba',
    '.z64', '.nes', '.gb', '.n64', '.psx', '.gbc'
]

PATTERNS_CORE = ['worker', 'api', 'translator', 'optimizer', 'manager', 'validator', 'utils']
PATTERNS_INTERFACE = ['ui', 'theme', 'gui', 'window', 'dialog', 'layout']

def safe_move(file_path, dest_folder):
    """Move arquivo com segurança, renomeando se já existir no destino."""
    if not dest_folder.exists():
        dest_folder.mkdir(parents=True, exist_ok=True)

    dest_path = dest_folder / file_path.name

    # Se já existe, renomeia (ex: arquivo_1.txt)
    counter = 1
    while dest_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        dest_path = dest_folder / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        shutil.move(str(file_path), str(dest_path))
        return True
    except Exception as e:
        print(f"   ❌ Erro ao mover: {e}")
        return False

def analyze_and_organize():
    print("="*60)
    print(f"🧹 SMART CLEANER - Iniciando faxina em: {BASE_DIR}")
    print("="*60)

    stats = {"lixo": 0, "roms": 0, "core": 0, "interface": 0, "config": 0, "mantidos": 0}

    # Lista tudo na raiz
    for item in os.listdir(BASE_DIR):
        item_path = BASE_DIR / item

        # Pular pastas e o próprio script
        if item_path.is_dir():
            if item == "__pycache__":
                safe_move(item_path, TRASH_DIR) # Move cache para lixo
                print(f"🗑️  Cache movido: {item}")
            continue

        if item in KEEP_IN_ROOT or item_path.name.startswith('.'):
            continue

        name_lower = item.lower()

        # 1. ANÁLISE DE LIXO
        is_lixo = False
        if item_path.suffix == '.log' or item_path.name == 'Thumbs.db' or item_path.name == '.DS_Store':
            is_lixo = True
        else:
            for pattern in PATTERNS_LIXO:
                if pattern in name_lower: # Verifica padrões no nome
                    # Proteção: Se for .py e tiver v5.3, não é lixo
                    if ".py" in name_lower and "v5.3" in name_lower:
                        continue
                    is_lixo = True
                    break

        if is_lixo:
            print(f"📄 Analisando: {item}")
            print(f"   ⚖️  Julgamento: LIXO")
            safe_move(item_path, TRASH_DIR)
            print(f"   🗑️  → _LIXEIRA_REVISAR/")
            stats["lixo"] += 1
            continue

        # 2. ANÁLISE DE ROMS
        if item_path.suffix.lower() in EXTENSIONS_ROMS:
            print(f"📄 Analisando: {item}")
            print(f"   ⚖️  Julgamento: ROM de Jogo")
            safe_move(item_path, ROMS_DIR)
            print(f"   🎮 → _INPUT_ROMS/")
            stats["roms"] += 1
            continue

        # 3. ANÁLISE DE CÓDIGO E CONFIG
        if item_path.suffix == '.json':
            print(f"📄 Analisando: {item}")
            print(f"   ⚖️  Julgamento: Configuração")
            safe_move(item_path, CONFIG_DIR)
            print(f"   ⚙️  → config/")
            stats["config"] += 1
            continue

        if item_path.suffix == '.py':
            # Interface
            if any(p in name_lower for p in PATTERNS_INTERFACE):
                print(f"📄 Analisando: {item}")
                print(f"   ⚖️  Julgamento: Interface")
                safe_move(item_path, INTERFACE_DIR)
                print(f"   🖼️  → interface/")
                stats["interface"] += 1
                continue

            # Core
            if any(p in name_lower for p in PATTERNS_CORE):
                print(f"📄 Analisando: {item}")
                print(f"   ⚖️  Julgamento: Core/Lógica")
                safe_move(item_path, CORE_DIR)
                print(f"   🧠 → core/")
                stats["core"] += 1
                continue

        stats["mantidos"] += 1

    print("\n" + "="*60)
    print("✅ LIMPEZA CONCLUÍDA!")
    print("="*60)
    print(f"🗑️  Arquivos movidos para Lixeira: {stats['lixo']}")
    print(f"🎮 ROMs organizadas: {stats['roms']}")
    print(f"🧠 Scripts Core organizados: {stats['core']}")
    print(f"🖼️  Scripts Interface organizados: {stats['interface']}")
    print(f"⚙️  Configs organizadas: {stats['config']}")
    print("-" * 30)
    print(f"📂 Verifique a pasta: {TRASH_DIR} antes de apagar definitivamente!")

if __name__ == "__main__":
    print(f"⚠️  ATENÇÃO: Este script irá organizar a pasta: {BASE_DIR}")
    confirm = input("Deseja continuar? (S/N): ").strip().lower()
    if confirm == 's':
        analyze_and_organize()
    else:
        print("Operação cancelada.")