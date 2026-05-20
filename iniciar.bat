@echo off
title AVD 360 - Grupo Gestao

echo.
echo ============================================================
echo   AVD 360 - Grupo Gestao Consultoria
echo   Iniciando sistema...
echo ============================================================
echo.

python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    python -m pip install -r requirements.txt
)

echo Iniciando servidor...
echo.
echo Acesse no navegador: http://localhost:8000
echo.
echo Para encerrar: feche esta janela
echo.

start /b cmd /c "timeout /t 3 >nul && start http://localhost:8000"

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
