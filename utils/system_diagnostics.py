# -*- coding: utf-8 -*-
"""
================================================================================
DIAGNÓSTICO COMPLETO - OLLAMA + CUDA + HARDWARE
Identifica gargalos e sugere otimizações
================================================================================
"""

import subprocess
import sys
import json
import time
import requests
import psutil
import platform
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

def check_cuda():
    """Verifica instalação e versão do CUDA"""
    print_header("1. CUDA / NVIDIA")

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            gpu_info = result.stdout.strip().split(", ")
            safe_print(f"GPU: {gpu_info[0]}")
            safe_print(f"Driver: {gpu_info[1]}")
            safe_print(f"VRAM Total: {gpu_info[2]}")
            safe_print(f"VRAM Usada: {gpu_info[3]}")
            safe_print(f"Utilizacao GPU: {gpu_info[4]}")
            safe_print("\nStatus: OK - CUDA detectado")
            return True
        else:
            safe_print("AVISO: nvidia-smi nao encontrado")
            return False
    except FileNotFoundError:
        safe_print("ERRO: NVIDIA driver nao instalado")
        safe_print("\nSOLUCAO:")
        safe_print("1. Baixe driver NVIDIA: https://www.nvidia.com/Download/index.aspx")
        safe_print("2. Instale CUDA Toolkit: https://developer.nvidia.com/cuda-downloads")
        return False
    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False

def check_ollama_status():
    """Verifica se Ollama está rodando"""
    print_header("2. OLLAMA STATUS")

    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)

        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])

            safe_print(f"Status: RODANDO")
            safe_print(f"Modelos instalados: {len(models)}")

            for model in models:
                name = model.get('name', 'Unknown')
                size = model.get('size', 0) / (1024**3)  # GB
                safe_print(f"  - {name} ({size:.2f} GB)")

            return True, models
        else:
            safe_print(f"Status: Ollama respondeu com codigo {response.status_code}")
            return False, []
    except requests.exceptions.ConnectionError:
        safe_print("Status: OFFLINE")
        safe_print("\nSOLUCAO:")
        safe_print("Execute: ollama serve")
        return False, []
    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False, []

def check_ollama_gpu_usage():
    """Verifica se Ollama está usando GPU"""
    print_header("3. OLLAMA GPU USAGE")

    safe_print("Fazendo requisicao de teste para verificar uso da GPU...")

    try:
        # Faz requisição de teste
        start = time.time()

        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3.1",
                "prompt": "Hello",
                "stream": False
            },
            timeout=30
        )

        elapsed = time.time() - start

        if response.status_code == 200:
            safe_print(f"Tempo de resposta: {elapsed:.2f}s")

            # Verifica uso de GPU durante processamento
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0:
                    gpu_util, mem_used = result.stdout.strip().split(", ")
                    safe_print(f"GPU Utilization: {gpu_util}")
                    safe_print(f"VRAM Usada: {mem_used}")

                    gpu_percent = int(gpu_util.replace(" %", ""))

                    if gpu_percent > 50:
                        safe_print("\nStatus: OK - Ollama ESTA usando GPU!")
                        return True
                    elif gpu_percent > 10:
                        safe_print("\nStatus: PARCIAL - GPU em uso, mas pode estar compartilhada")
                        safe_print("Dica: Feche outros apps que usam GPU")
                        return True
                    else:
                        safe_print("\nAVISO: GPU com uso baixo - pode estar usando CPU")
                        safe_print("\nSOLUCAO:")
                        safe_print("1. Reinstale Ollama com suporte CUDA")
                        safe_print("2. Verifique: ollama run llama3.1 --verbose")
                        return False
            except:
                pass

            # Fallback: analisa tempo de resposta
            if elapsed < 3:
                safe_print("\nStatus: PROVAVEL GPU (resposta rapida)")
                return True
            else:
                safe_print("\nAVISO: Resposta lenta - pode estar usando CPU")
                safe_print(f"Tempo esperado com GPU: <3s | Tempo atual: {elapsed:.1f}s")
                return False
        else:
            safe_print(f"ERRO: Status {response.status_code}")
            return False

    except Exception as e:
        safe_print(f"ERRO: {e}")
        return False

def check_system_resources():
    """Verifica recursos do sistema"""
    print_header("4. RECURSOS DO SISTEMA")

    # CPU
    cpu_count = psutil.cpu_count(logical=True)
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()

    safe_print(f"CPU: {platform.processor()}")
    safe_print(f"Nucleos (logicos): {cpu_count}")
    safe_print(f"Frequencia: {cpu_freq.current:.0f} MHz")
    safe_print(f"Uso atual: {cpu_percent:.1f}%")

    # RAM
    ram = psutil.virtual_memory()
    ram_total_gb = ram.total / (1024**3)
    ram_used_gb = ram.used / (1024**3)
    ram_percent = ram.percent

    safe_print(f"\nRAM Total: {ram_total_gb:.1f} GB")
    safe_print(f"RAM Usada: {ram_used_gb:.1f} GB ({ram_percent:.1f}%)")
    safe_print(f"RAM Disponivel: {(ram_total_gb - ram_used_gb):.1f} GB")

    # Disco
    disk = psutil.disk_usage('/')
    disk_total_gb = disk.total / (1024**3)
    disk_free_gb = disk.free / (1024**3)

    safe_print(f"\nDisco Total: {disk_total_gb:.0f} GB")
    safe_print(f"Disco Livre: {disk_free_gb:.0f} GB")

    return {
        'cpu_cores': cpu_count,
        'ram_gb': ram_total_gb,
        'ram_available_gb': ram_total_gb - ram_used_gb
    }

def recommend_settings(system_info, gpu_available):
    """Recomenda configurações otimizadas"""
    print_header("5. RECOMENDACOES OTIMIZADAS")

    cpu_cores = system_info['cpu_cores']
    ram_gb = system_info['ram_gb']

    if gpu_available:
        # GTX 1060 6GB + GPU otimizado
        workers = 2  # 2 workers ideal para 6GB VRAM
        batch_size = 2
        timeout = 90

        safe_print("CONFIGURACAO: GPU Otimizada (GTX 1060 6GB)")
        safe_print(f"Workers: {workers} (ideal para 6GB VRAM)")
        safe_print(f"Batch Size: {batch_size}")
        safe_print(f"Timeout: {timeout}s")
        safe_print("\nESTIMATIVA: ~40-60 textos/s")
        safe_print("TEMPO TOTAL (41k textos): ~12-15 min")
    else:
        # CPU fallback
        workers = min(2, cpu_cores // 2)
        batch_size = 1
        timeout = 180

        safe_print("CONFIGURACAO: CPU Mode (GPU nao detectada)")
        safe_print(f"Workers: {workers}")
        safe_print(f"Batch Size: {batch_size}")
        safe_print(f"Timeout: {timeout}s (maior para CPU)")
        safe_print("\nAVISO: Modo CPU e MUITO mais lento")
        safe_print("ESTIMATIVA: ~5-10 textos/s")
        safe_print("TEMPO TOTAL (41k textos): ~1-2 horas")
        safe_print("\nRECOMENDACAO: Ative GPU para 6-10x mais rapido!")

    # Configurações avançadas do Ollama
    safe_print("\n" + "-"*70)
    safe_print("CONFIGURACOES AVANCADAS DO OLLAMA:")
    safe_print("-"*70)

    if gpu_available:
        safe_print("\nCrie/edite: C:\\Users\\celso\\.ollama\\config.json")
        safe_print("""
{
  "num_parallel": 2,
  "num_gpu": 1,
  "num_thread": 6,
  "num_ctx": 2048,
  "gpu_layers": 35
}
        """)

        safe_print("\nVariaveis de ambiente (opcional):")
        safe_print("set OLLAMA_NUM_PARALLEL=2")
        safe_print("set OLLAMA_MAX_LOADED_MODELS=1")
        safe_print("set CUDA_VISIBLE_DEVICES=0")
    else:
        safe_print("\nPara ativar GPU:")
        safe_print("1. Instale NVIDIA Driver + CUDA Toolkit")
        safe_print("2. Reinstale Ollama: https://ollama.com/download")
        safe_print("3. Execute: ollama serve")

    return {
        'workers': workers,
        'batch_size': batch_size,
        'timeout': timeout
    }

def benchmark_translation(workers, timeout):
    """Faz benchmark de tradução"""
    print_header("6. BENCHMARK DE TRADUCAO")

    safe_print("Testando traducao de 10 textos de exemplo...")

    test_texts = [
        "Hello, how are you?",
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is transforming the world.",
        "Video games are a form of interactive entertainment.",
        "The weather today is quite pleasant.",
        "Programming requires logical thinking.",
        "Music has the power to evoke emotions.",
        "Science and technology advance rapidly.",
        "Reading books expands knowledge.",
        "Friendship is a valuable treasure."
    ]

    start = time.time()
    success_count = 0

    for i, text in enumerate(test_texts, 1):
        try:
            response = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "llama3.1",
                    "prompt": f"Traduza para portugues: {text}",
                    "stream": False
                },
                timeout=timeout
            )

            if response.status_code == 200:
                success_count += 1
                safe_print(f"[{i}/10] OK")
            else:
                safe_print(f"[{i}/10] ERRO: Status {response.status_code}")

        except requests.exceptions.Timeout:
            safe_print(f"[{i}/10] TIMEOUT")
        except Exception as e:
            safe_print(f"[{i}/10] ERRO: {e}")

    elapsed = time.time() - start

    safe_print(f"\nResultados:")
    safe_print(f"Sucesso: {success_count}/10 ({success_count*10}%)")
    safe_print(f"Tempo total: {elapsed:.2f}s")
    safe_print(f"Taxa: {success_count/elapsed:.2f} textos/s")

    if success_count >= 8:
        safe_print("\nStatus: OTIMO - Sistema estavel")
    elif success_count >= 5:
        safe_print("\nStatus: BOM - Pode melhorar com ajustes")
    else:
        safe_print("\nStatus: RUIM - Precisa de otimizacao urgente")

    return {
        'success_rate': success_count / 10,
        'rate': success_count / elapsed if elapsed > 0 else 0
    }

def main():
    safe_print("\n" + "="*70)
    safe_print("DIAGNOSTICO COMPLETO - PIPELINE DE TRADUCAO")
    safe_print("="*70)

    # 1. CUDA
    cuda_ok = check_cuda()

    # 2. Ollama Status
    ollama_ok, models = check_ollama_status()

    if not ollama_ok:
        safe_print("\n" + "!"*70)
        safe_print("CRITICO: Ollama nao esta rodando!")
        safe_print("Execute: ollama serve")
        safe_print("!"*70)
        return

    # 3. GPU Usage
    gpu_ok = check_ollama_gpu_usage()

    # 4. System Resources
    system_info = check_system_resources()

    # 5. Recomendações
    settings = recommend_settings(system_info, gpu_ok)

    # 6. Benchmark
    if ollama_ok:
        benchmark_translation(settings['workers'], settings['timeout'])

    # Resumo Final
    print_header("RESUMO FINAL")

    safe_print(f"CUDA/GPU: {'OK' if cuda_ok else 'NAO DETECTADO'}")
    safe_print(f"Ollama: {'RODANDO' if ollama_ok else 'OFFLINE'}")
    safe_print(f"GPU Usage: {'SIM' if gpu_ok else 'NAO (usando CPU)'}")

    safe_print(f"\nCONFIGURACOES RECOMENDADAS:")
    safe_print(f"  Workers: {settings['workers']}")
    safe_print(f"  Timeout: {settings['timeout']}s")
    safe_print(f"  Batch Size: {settings['batch_size']}")

    if not gpu_ok:
        safe_print("\n" + "!"*70)
        safe_print("ATENCAO: GPU nao esta sendo usada!")
        safe_print("Traducao sera 6-10x MAIS LENTA")
        safe_print("!"*70)

    safe_print("\n" + "="*70)
    safe_print("Diagnostico concluido!")
    safe_print("="*70)

if __name__ == "__main__":
    main()