@echo off
title AVD 360 - Instalacao

echo.
echo ============================================================
echo   AVD 360 - Grupo Gestao Consultoria
echo   Script de Instalacao
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Baixe e instale o Python em:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Marque "Add Python to PATH" na instalacao.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
python --version

echo.
echo Atualizando pip...
python -m pip install --upgrade pip

echo.
echo Instalando dependencias. Aguarde...
echo.

python -m pip install -r requirements.txt --upgrade

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar dependencias.
    echo Verifique sua conexao com a internet e tente novamente.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Instalacao concluida com sucesso!
echo ============================================================
echo.
echo Para iniciar o sistema, execute: iniciar.bat
echo.
echo Email: admin@grupogestao.com.br
echo Senha: Admin@2024
echo.
pause
