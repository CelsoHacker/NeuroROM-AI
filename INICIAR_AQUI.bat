@echo off
setlocal

cd /d "%~dp0"

if exist "rom-translation-framework\main.py" (
  cd /d "rom-translation-framework"
)

set "PYTHON_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  set "PYTHON_CMD=py -3"
)

if exist "main.py" (
  call %PYTHON_CMD% "main.py"
  if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar pelo main.py.
    pause
  )
  goto :eof
)

if exist "interface\interface_tradutor_final.py" (
  call %PYTHON_CMD% "interface\interface_tradutor_final.py"
  if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar pela interface principal.
    pause
  )
  goto :eof
)

echo [ERRO] Nao encontrei main.py nem o arquivo da interface.
pause
