@echo off
REM ============================================================================
REM INICIAR OLLAMA - NeuroROM AI v5.3
REM ============================================================================
REM Script para iniciar o Ollama facilmente
REM ============================================================================

echo.
echo ╔═══════════════════════════════════════════════════════════════════════════╗
echo ║                    INICIANDO OLLAMA - NeuroROM AI v5.3                     ║
echo ╚═══════════════════════════════════════════════════════════════════════════╝
echo.

REM Verifica se Ollama está instalado
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ ERRO: Ollama não está instalado!
    echo.
    echo 💡 SOLUÇÃO:
    echo    1. Baixe o Ollama: https://ollama.com/download
    echo    2. Instale e reinicie o terminal
    echo    3. Execute este script novamente
    echo.
    pause
    exit /b 1
)

echo ✅ Ollama encontrado!
echo.

REM Verifica versão
echo 📦 Versão do Ollama:
ollama --version
echo.

REM Verifica modelos instalados
echo 📚 Modelos instalados:
ollama list
echo.

echo ════════════════════════════════════════════════════════════════════════════
echo 🚀 INICIANDO SERVIÇO OLLAMA...
echo ════════════════════════════════════════════════════════════════════════════
echo.
echo ⚠️  IMPORTANTE: NÃO FECHE ESTA JANELA ENQUANTO ESTIVER TRADUZINDO!
echo.
echo 💡 Para parar o Ollama: Pressione Ctrl+C
echo.
echo ════════════════════════════════════════════════════════════════════════════
echo.

REM Inicia Ollama
ollama serve
