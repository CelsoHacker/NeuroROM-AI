#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 Verificador do Sistema - ROM Translation Framework v5.3

Este script verifica se todos os componentes estão instalados e funcionando.
Execute antes de começar a traduzir!

Uso:
    python verificar_sistema.py
"""

import sys
import os
from pathlib import Path

print("\n" + "="*70)
print("🔍 VERIFICADOR DO SISTEMA - ROM Translation Framework v5.3")
print("="*70 + "\n")

# Cores para terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check(name, condition, fix_tip=""):
    """Verifica uma condição e exibe resultado"""
    if condition:
        print(f"  ✅ {GREEN}{name}{RESET}")
        return True
    else:
        print(f"  ❌ {RED}{name}{RESET}")
        if fix_tip:
            print(f"     💡 {YELLOW}{fix_tip}{RESET}")
        return False

print("📦 VERIFICANDO DEPENDÊNCIAS PYTHON\n")

# Python version
python_version = sys.version_info
python_ok = python_version >= (3, 8)
check(
    f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
    python_ok,
    "Atualize para Python 3.8+ (https://python.org)"
)

# PyQt6
try:
    import PyQt6
    pyqt_ok = True
except ImportError:
    pyqt_ok = False

check(
    "PyQt6 (Interface gráfica)",
    pyqt_ok,
    "Instale: pip install PyQt6"
)

# Requests
try:
    import requests
    requests_ok = True
except ImportError:
    requests_ok = False

check(
    "Requests (HTTP client)",
    requests_ok,
    "Instale: pip install requests"
)

# Google Generative AI
try:
    import google.generativeai
    gemini_ok = True
except ImportError:
    gemini_ok = False

check(
    "Google Generative AI (Gemini API)",
    gemini_ok,
    "Instale: pip install google-generativeai"
)

print("\n" + "="*70)
print("📁 VERIFICANDO ARQUIVOS PRINCIPAIS\n")

# Arquivos essenciais
essential_files = {
    "Interface principal": "rom-translation-framework/interface/interface_tradutor_final.py",
    "API Gemini": "rom-translation-framework/interface/gemini_api.py",
    "Quota Manager": "rom-translation-framework/core/quota_manager.py",
    "Hybrid Translator": "rom-translation-framework/core/hybrid_translator.py",
    "Batch Queue Manager": "rom-translation-framework/core/batch_queue_manager.py",
    "Otimizador": "otimizar_arquivo_traducao.py",
}

all_files_ok = True
for name, filepath in essential_files.items():
    exists = Path(filepath).exists()
    all_files_ok &= check(name, exists, f"Arquivo faltando: {filepath}")

print("\n" + "="*70)
print("🔧 VERIFICANDO SERVIÇOS EXTERNOS\n")

# Ollama
try:
    response = requests.get('http://localhost:11434/api/tags', timeout=2)
    if response.status_code == 200:
        models = response.json().get('models', [])
        ollama_ok = True
        print(f"  ✅ {GREEN}Ollama rodando ({len(models)} modelos){RESET}")

        # Verifica se tem llama3.2:3b
        has_llama = any('llama3.2' in m.get('name', '') for m in models)
        if has_llama:
            print(f"     ✅ Modelo llama3.2:3b instalado")
        else:
            print(f"     ⚠️ {YELLOW}Modelo llama3.2:3b não encontrado{RESET}")
            print(f"     💡 Instale: ollama pull llama3.2:3b")
    else:
        ollama_ok = False
        check("Ollama", False, "Inicie: ollama serve")
except Exception as e:
    ollama_ok = False
    check("Ollama", False, "Inicie: ollama serve (ou instale do ollama.ai)")

# Gemini API Key
gemini_key = os.getenv('GEMINI_API_KEY', '')
has_gemini_key = len(gemini_key) > 10

check(
    "Gemini API Key configurada",
    has_gemini_key,
    "Configure variável GEMINI_API_KEY ou cole na interface"
)

print("\n" + "="*70)
print("💾 VERIFICANDO ESPAÇO EM DISCO\n")

import shutil
disk = shutil.disk_usage(".")
free_gb = disk.free / (1024**3)
has_space = free_gb > 5

check(
    f"Espaço livre: {free_gb:.1f} GB",
    has_space,
    "Libere mais espaço (mínimo 5GB)"
)

print("\n" + "="*70)
print("🎮 VERIFICANDO GPU (OPCIONAL)\n")

try:
    import subprocess
    result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.free', '--format=csv,noheader'],
                          capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        gpu_info = result.stdout.strip().split(',')
        gpu_name = gpu_info[0].strip()
        gpu_memory = gpu_info[1].strip()
        print(f"  ✅ {GREEN}GPU detectada: {gpu_name}{RESET}")
        print(f"     💾 VRAM livre: {gpu_memory}")
    else:
        print(f"  ⚠️ {YELLOW}GPU NVIDIA não detectada{RESET}")
        print(f"     💡 Ollama funcionará mais lento sem GPU")
except Exception:
    print(f"  ⚠️ {YELLOW}nvidia-smi não encontrado{RESET}")
    print(f"     💡 GPU não é obrigatória, mas acelera Ollama")

print("\n" + "="*70)
print("📊 RESUMO\n")

# Calcula score
checks_passed = [
    python_ok,
    pyqt_ok,
    requests_ok,
    gemini_ok,
    all_files_ok,
    has_space
]

score = sum(checks_passed) / len(checks_passed) * 100

if score >= 90:
    status_emoji = "🎉"
    status_text = f"{GREEN}EXCELENTE! Sistema pronto para usar!{RESET}"
elif score >= 70:
    status_emoji = "✅"
    status_text = f"{GREEN}BOM! Sistema funcional, mas pode melhorar.{RESET}"
elif score >= 50:
    status_emoji = "⚠️"
    status_text = f"{YELLOW}ATENÇÃO! Alguns componentes faltando.{RESET}"
else:
    status_emoji = "❌"
    status_text = f"{RED}ERRO! Muitos componentes faltando.{RESET}"

print(f"{status_emoji} Status: {status_text}")
print(f"📈 Score: {score:.0f}%")

print("\n" + "="*70)
print("🚀 PRÓXIMOS PASSOS\n")

if score >= 90:
    print("  ✅ Tudo pronto! Você pode começar a traduzir agora.")
    print()
    print("  Para começar:")
    print("     1. Execute: python rom-translation-framework/interface/interface_tradutor_final.py")
    print("     2. OU execute: INICIAR_AQUI.bat (Windows)")
    print("     3. Escolha modo: 🤖 Auto (Gemini → Ollama)")
    print("     4. Carregue seu arquivo e traduza!")
    print()
    print("  📖 Leia: LEIA_PRIMEIRO.md para mais detalhes")

elif score >= 70:
    print("  ⚠️ Sistema funcional, mas instale os componentes faltando:")
    print()
    if not pyqt_ok:
        print("     pip install PyQt6")
    if not requests_ok:
        print("     pip install requests")
    if not gemini_ok:
        print("     pip install google-generativeai")
    if not ollama_ok:
        print("     • Instale Ollama de: https://ollama.ai/download")
        print("     • Execute: ollama serve")
        print("     • Baixe modelo: ollama pull llama3.2:3b")
    if not has_gemini_key:
        print("     • Configure API Key: export GEMINI_API_KEY='sua_key'")

else:
    print("  ❌ Muitos componentes faltando. Siga este guia:")
    print()
    print("  1. Atualize Python para 3.8+")
    print("  2. Instale dependências:")
    print("     pip install PyQt6 requests google-generativeai")
    print()
    print("  3. (Opcional) Instale Ollama:")
    print("     • https://ollama.ai/download")
    print("     • ollama pull llama3.2:3b")
    print()
    print("  4. Execute este script novamente para verificar")

print("\n" + "="*70)
print("📞 SUPORTE\n")
print("  📖 Documentação: LEIA_PRIMEIRO.md")
print("  📊 Fluxogramas: DIAGRAMA_FLUXO.md")
print("  📚 Índice completo: INDICE_COMPLETO.md")
print()
print("="*70 + "\n")

# Retorna código de saída
sys.exit(0 if score >= 70 else 1)
