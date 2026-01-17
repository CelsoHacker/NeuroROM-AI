# -*- coding: utf-8 -*-
"""
================================================================================
FIX CUDA ERRORS - Diagnóstico e Correção Definitiva
Resolve: "llama runner process has terminated: CUDA error"
================================================================================
"""

import subprocess
import sys
import json
import time
import requests
import os
from pathlib import Path

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        sys.stdout.write(text.encode("utf-8", errors="replace").decode("utf-8") + "\n")

def print_header(title):
    safe_print(f"\n{'='*70}")
    safe_print(f"{title}")
    safe_print(f"{'='*70}")

# ============================================================================
# DIAGNÓSTICO 1: VRAM FRAGMENTATION
# ============================================================================
def check_vram_fragmentation():
    print_header("1. VRAM FRAGMENTATION CHECK")

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            total, used, free = map(int, result.stdout.strip().split(", "))

            safe_print(f"VRAM Total: {total} MB")
            safe_print(f"VRAM Usada: {used} MB")
            safe_print(f"VRAM Livre: {free} MB")

            # Análise crítica
            if used > 4500:
                safe_print("\n[CRITICO] VRAM muito alta ANTES da traducao!")
                safe_print("Causa provavel: Modelo nao foi descarregado corretamente")
                safe_print("\nSOLUCAO:")
                safe_print("1. Feche todos os programas que usam GPU")
                safe_print("2. Reinicie o Ollama")
                return False
            elif free < 1500:
                safe_print("\n[AVISO] VRAM livre baixa")
                safe_print("Pode causar erros CUDA durante traducao")
                return False
            else:
                safe_print("\n[OK] VRAM adequada para traducao")
                return True
    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False

# ============================================================================
# DIAGNÓSTICO 2: MODELO SOBRECARREGADO
# ============================================================================
def check_model_layers():
    print_header("2. MODEL GPU LAYERS CHECK")

    try:
        # Verifica informações do modelo
        response = requests.post(
            "http://127.0.0.1:11434/api/show",
            json={"name": "llama3.1"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            modelfile = data.get('modelfile', '')

            safe_print("Modelfile atual:")
            safe_print(modelfile[:500])

            # Procura por gpu_layers
            if 'num_gpu' in modelfile:
                safe_print("\n[INFO] Modelo configurado com GPU")
            else:
                safe_print("\n[AVISO] Configuracao GPU nao detectada")

            return True
    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False

# ============================================================================
# DIAGNÓSTICO 3: CUDA OUT OF MEMORY
# ============================================================================
def test_cuda_stability():
    print_header("3. CUDA STABILITY TEST")

    safe_print("Testando 5 requisicoes consecutivas para detectar crash...")

    crashes = 0
    for i in range(1, 6):
        try:
            safe_print(f"\n[{i}/5] Testando...", end=" ", flush=True)

            response = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "llama3.1",
                    "prompt": "Hello",
                    "stream": False,
                    "options": {
                        "num_ctx": 512,  # Contexto reduzido
                        "num_predict": 10
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                safe_print("OK")
            else:
                safe_print(f"ERRO: Status {response.status_code}")
                crashes += 1

        except requests.exceptions.Timeout:
            safe_print("TIMEOUT")
            crashes += 1
        except requests.exceptions.ConnectionError:
            safe_print("CRASH - Ollama parou de responder")
            crashes += 1
            break
        except Exception as e:
            safe_print(f"ERRO: {e}")
            crashes += 1

        time.sleep(2)

    if crashes == 0:
        safe_print("\n[OK] Nenhum crash detectado - Sistema estavel")
        return True
    else:
        safe_print(f"\n[CRITICO] {crashes}/5 crashes detectados!")
        safe_print("\nCausa provavel:")
        safe_print("1. GPU layers muito alto (modelo grande demais)")
        safe_print("2. CUDA out of memory")
        safe_print("3. Driver NVIDIA instavel")
        return False

# ============================================================================
# SOLUÇÃO 1: REDUZIR GPU LAYERS
# ============================================================================
def fix_reduce_gpu_layers():
    print_header("SOLUCAO 1: REDUZIR GPU LAYERS")

    safe_print("Criando modelo otimizado para GTX 1060 6GB...")

    modelfile = """
FROM llama3.1

# Otimizacoes para GTX 1060 6GB
PARAMETER num_ctx 512
PARAMETER num_batch 256
PARAMETER num_gpu 20
PARAMETER num_thread 4
PARAMETER stop [INST]
PARAMETER stop [/INST]
"""

    # Salva Modelfile
    modelfile_path = Path("Modelfile.gtx1060")
    with open(modelfile_path, 'w') as f:
        f.write(modelfile)

    safe_print(f"Modelfile salvo: {modelfile_path}")
    safe_print("\nExecutando: ollama create llama3.1-gtx1060 -f Modelfile.gtx1060")

    try:
        result = subprocess.run(
            ["ollama", "create", "llama3.1-gtx1060", "-f", str(modelfile_path)],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            safe_print("\n[OK] Modelo otimizado criado: llama3.1-gtx1060")
            safe_print("\nUSO:")
            safe_print("  Na interface, altere o MODEL para: llama3.1-gtx1060")
            safe_print("  Ou edite tradutor_paralelo_v4.py linha ~73:")
            safe_print("  MODEL = 'llama3.1-gtx1060'")
            return True
        else:
            safe_print(f"\nERRO: {result.stderr}")
            return False
    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False

# ============================================================================
# SOLUÇÃO 2: CONFIGURAR VARIÁVEIS DE AMBIENTE
# ============================================================================
def fix_environment_variables():
    print_header("SOLUCAO 2: VARIAVEIS DE AMBIENTE")

    safe_print("Configure estas variaveis ANTES de iniciar Ollama:")
    safe_print("")
    safe_print("# Limite de VRAM (4.5GB dos 6GB)")
    safe_print("set CUDA_MEMORY_FRACTION=0.75")
    safe_print("")
    safe_print("# Desabilita cache agressivo")
    safe_print("set OLLAMA_KEEP_ALIVE=0")
    safe_print("")
    safe_print("# Limita paralelismo")
    safe_print("set OLLAMA_NUM_PARALLEL=1")
    safe_print("set OLLAMA_MAX_LOADED_MODELS=1")
    safe_print("")
    safe_print("# GPU especifica")
    safe_print("set CUDA_VISIBLE_DEVICES=0")
    safe_print("")
    safe_print("# Depois inicie:")
    safe_print("ollama serve")
    safe_print("")

    # Cria script batch
    batch_script = """@echo off
echo Configurando ambiente para GTX 1060 6GB...

set CUDA_MEMORY_FRACTION=0.75
set OLLAMA_KEEP_ALIVE=0
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_MAX_LOADED_MODELS=1
set CUDA_VISIBLE_DEVICES=0

echo.
echo Iniciando Ollama...
ollama serve
"""

    batch_path = Path("start_ollama_gtx1060.bat")
    with open(batch_path, 'w') as f:
        f.write(batch_script)

    safe_print(f"Script criado: {batch_path}")
    safe_print("\nUSO:")
    safe_print(f"  Execute: {batch_path}")
    safe_print("  Em vez de: ollama serve")

# ============================================================================
# SOLUÇÃO 3: USAR MODELO MENOR
# ============================================================================
def fix_use_smaller_model():
    print_header("SOLUCAO 3: MODELO MENOR")

    safe_print("Voce tem llama3.2:3b instalado (mais leve)")
    safe_print("")
    safe_print("TESTE:")
    safe_print("1. Use llama3.2:3b em vez de llama3.1")
    safe_print("2. Edite tradutor_paralelo_v4.py linha ~73:")
    safe_print("   MODEL = 'llama3.2:3b'")
    safe_print("")
    safe_print("VANTAGENS:")
    safe_print("  - Usa ~2GB VRAM (vs ~4-5GB do llama3.1)")
    safe_print("  - Mais rapido")
    safe_print("  - Menos crashes")
    safe_print("")
    safe_print("DESVANTAGENS:")
    safe_print("  - Qualidade de traducao um pouco menor")
    safe_print("  - Mas suficiente para jogos")

# ============================================================================
# SOLUÇÃO 4: LIMPAR CACHE CUDA
# ============================================================================
def fix_clear_cuda_cache():
    print_header("SOLUCAO 4: LIMPAR CACHE CUDA")

    safe_print("Execute estes comandos:")
    safe_print("")
    safe_print("# Pare Ollama")
    safe_print("taskkill /F /IM ollama.exe")
    safe_print("taskkill /F /IM ollama_llama_server.exe")
    safe_print("")
    safe_print("# Limpe cache CUDA")
    safe_print("nvidia-smi --gpu-reset")
    safe_print("")
    safe_print("# Aguarde 5 segundos")
    safe_print("timeout /t 5")
    safe_print("")
    safe_print("# Reinicie Ollama")
    safe_print("ollama serve")

    # Cria script
    reset_script = """@echo off
echo Limpando cache CUDA...

taskkill /F /IM ollama.exe 2>nul
taskkill /F /IM ollama_llama_server.exe 2>nul

timeout /t 2 >nul

nvidia-smi --gpu-reset

echo.
echo Cache limpo! Aguarde 5 segundos...
timeout /t 5 >nul

echo.
echo Pronto para reiniciar Ollama
echo Execute: ollama serve
pause
"""

    script_path = Path("reset_cuda_cache.bat")
    with open(script_path, 'w') as f:
        f.write(reset_script)

    safe_print("")
    safe_print(f"Script criado: {script_path}")
    safe_print("\nUSO:")
    safe_print(f"  Execute: {script_path}")
    safe_print("  Quando Ollama crashar")

# ============================================================================
# SOLUÇÃO 5: CONFIGURAR TRADUTOR
# ============================================================================
def fix_translator_config():
    print_header("SOLUCAO 5: CONFIGURAR TRADUTOR")

    safe_print("Ajustes CRITICOS para GTX 1060 6GB:")
    safe_print("")
    safe_print("Na interface grafica:")
    safe_print("  Workers: 1 (NUNCA mais que 1)")
    safe_print("  Timeout: 60s (mais curto)")
    safe_print("  Batch Size: 1")
    safe_print("")
    safe_print("Edite tradutor_paralelo_v4.py:")
    safe_print("")
    safe_print("# Linha ~73 - Use modelo menor")
    safe_print("MODEL = 'llama3.2:3b'  # Mais leve")
    safe_print("")
    safe_print("# Linha ~74-75 - Timeouts mais curtos")
    safe_print("BASE_TIMEOUT = 60  # Era 120")
    safe_print("MAX_TIMEOUT = 120  # Era 300")
    safe_print("")
    safe_print("# Linha ~51 - Workers = 1 FIXO")
    safe_print("MAX_WORKERS = 1  # NUNCA mais que 1")
    safe_print("")
    safe_print("# Adicione no payload (linha ~502):")
    safe_print("""
payload = {
    'model': Config.MODEL,
    'prompt': prompt,
    'stream': False,
    'options': {
        'temperature': 0.3,
        'top_p': 0.9,
        'num_ctx': 512,        # NOVO: Contexto reduzido
        'num_predict': 100,     # NOVO: Resposta curta
        'num_batch': 128        # NOVO: Batch menor
    }
}
""")

# ============================================================================
# MAIN
# ============================================================================
def main():
    safe_print("\n" + "="*70)
    safe_print("FIX CUDA ERRORS - GTX 1060 6GB")
    safe_print("="*70)

    # Diagnósticos
    vram_ok = check_vram_fragmentation()
    model_ok = check_model_layers()
    cuda_ok = test_cuda_stability()

    # Soluções
    print_header("SOLUCOES RECOMENDADAS")

    if not cuda_ok:
        safe_print("\n[CRITICO] Crashes CUDA detectados!")
        safe_print("\nAplique TODAS as solucoes abaixo:")
        safe_print("")

        # Todas as soluções
        fix_reduce_gpu_layers()
        fix_environment_variables()
        fix_use_smaller_model()
        fix_clear_cuda_cache()
        fix_translator_config()

        # Resumo final
        print_header("RESUMO - ORDEM DE EXECUCAO")
        safe_print("")
        safe_print("1. Execute: reset_cuda_cache.bat")
        safe_print("2. Execute: start_ollama_gtx1060.bat")
        safe_print("3. Edite tradutor_paralelo_v4.py:")
        safe_print("   - MODEL = 'llama3.2:3b'")
        safe_print("   - MAX_WORKERS = 1")
        safe_print("   - BASE_TIMEOUT = 60")
        safe_print("   - Adicione opcoes no payload")
        safe_print("4. Configure interface:")
        safe_print("   - Workers: 1")
        safe_print("   - Timeout: 60s")
        safe_print("5. Teste com 10 textos primeiro")
        safe_print("")
        safe_print("Se continuar crashando:")
        safe_print("  - Use APENAS llama3.2:3b")
        safe_print("  - Feche Chrome/Discord/OBS")
        safe_print("  - Considere traducao CPU (lenta mas estavel)")

    else:
        safe_print("\n[OK] Sistema estavel!")
        safe_print("\nMas aplique estas otimizacoes preventivas:")
        safe_print("1. Workers: 1 (nunca mais)")
        safe_print("2. Use llama3.2:3b (mais leve)")
        safe_print("3. Timeout: 60s")

    safe_print("\n" + "="*70)
    safe_print("Scripts criados:")
    safe_print("  - Modelfile.gtx1060")
    safe_print("  - start_ollama_gtx1060.bat")
    safe_print("  - reset_cuda_cache.bat")
    safe_print("="*70)

if __name__ == "__main__":
    main()