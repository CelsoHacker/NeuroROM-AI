@echo off
chcp 65001 >nul
color 0A
title 🎮 ROM Translation Framework v5.3

cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  🎮 ROM TRANSLATION FRAMEWORK v5.3
echo ═══════════════════════════════════════════════════════════════════
echo.
echo  Escolha uma opção:
echo.
echo  [1] 🚀 Abrir Interface de Tradução (RECOMENDADO)
echo  [2] 📊 Otimizar Arquivo (Remover Duplicatas)
echo  [3] 📖 Ver Documentação
echo  [4] 🧪 Testar Ollama
echo  [5] ❌ Sair
echo.
echo ═══════════════════════════════════════════════════════════════════
echo.

set /p opcao="Digite o número da opção: "

if "%opcao%"=="1" goto interface
if "%opcao%"=="2" goto otimizar
if "%opcao%"=="3" goto docs
if "%opcao%"=="4" goto testar
if "%opcao%"=="5" goto sair

echo Opção inválida!
timeout /t 2 >nul
goto inicio

:interface
cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  🚀 ABRINDO INTERFACE DE TRADUÇÃO
echo ═══════════════════════════════════════════════════════════════════
echo.
echo  ✅ Modo recomendado: 🤖 Auto (Gemini → Ollama)
echo  ✅ Workers: 3
echo  ✅ Use o botão ⏹️ PARAR para pausar quando quiser
echo.
echo  Abrindo em 3 segundos...
timeout /t 3 >nul
cd /d "%~dp0"
python interface\interface_tradutor_final.py
goto fim

:otimizar
cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  📊 OTIMIZAR ARQUIVO (REMOVER DUPLICATAS)
echo ═══════════════════════════════════════════════════════════════════
echo.
echo  Este script remove linhas duplicadas do seu arquivo de tradução,
echo  reduzindo o tempo de processamento em 50-80%%!
echo.
echo  Arraste seu arquivo para esta janela e pressione ENTER:
echo.
set /p arquivo="Arquivo: "

if not exist %arquivo% (
    echo.
    echo ❌ Arquivo não encontrado!
    timeout /t 3 >nul
    goto inicio
)

echo.
echo ⏳ Otimizando... Aguarde...
python otimizar_arquivo_traducao.py %arquivo%

echo.
echo ✅ Pronto! Use o arquivo _unique.txt na interface.
echo.
pause
goto inicio

:docs
cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  📖 DOCUMENTAÇÃO DISPONÍVEL
echo ═══════════════════════════════════════════════════════════════════
echo.
echo  [1] LEIA_PRIMEIRO.md - Guia completo de uso
echo  [2] GUIA_OTIMIZACAO_RAPIDA.md - Como otimizar arquivos grandes
echo  [3] GUIA_MODO_HIBRIDO.md - Modo Auto (Gemini + Ollama)
echo  [4] RELATORIO_OLLAMA_GPU.md - Análise de temperatura/GPU
echo  [5] INICIO_RAPIDO_QUOTA.md - Sistema de quota Gemini
echo  [6] Voltar
echo.
set /p doc="Escolha um documento: "

if "%doc%"=="1" start LEIA_PRIMEIRO.md
if "%doc%"=="2" start GUIA_OTIMIZACAO_RAPIDA.md
if "%doc%"=="3" start GUIA_MODO_HIBRIDO.md
if "%doc%"=="4" start RELATORIO_OLLAMA_GPU.md
if "%doc%"=="5" start INICIO_RAPIDO_QUOTA.md
if "%doc%"=="6" goto inicio

timeout /t 2 >nul
goto docs

:testar
cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  🧪 TESTANDO OLLAMA
echo ═══════════════════════════════════════════════════════════════════
echo.
echo  Verificando se Ollama está rodando...
echo.

curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel%==0 (
    echo  ✅ Ollama está RODANDO!
    echo.
    echo  Modelos instalados:
    curl -s http://127.0.0.1:11434/api/tags
    echo.
    echo  ✅ Tudo OK! Você pode usar o modo Ollama.
) else (
    echo  ❌ Ollama NÃO está rodando!
    echo.
    echo  Para iniciar:
    echo    1. Abra outro terminal
    echo    2. Digite: ollama serve
    echo    3. Execute este teste novamente
)

echo.
pause
goto inicio

:sair
cls
echo.
echo ═══════════════════════════════════════════════════════════════════
echo  👋 Até logo!
echo ═══════════════════════════════════════════════════════════════════
echo.
timeout /t 2 >nul
exit

:fim
goto inicio
