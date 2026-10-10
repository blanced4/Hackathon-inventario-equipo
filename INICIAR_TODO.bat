@echo off
title [SPINDLE-OS] Sistema de Inventario Inteligente - HackaTecNM
color 0B
echo ======================================================================
echo    INICIANDO SERVICIO DE INVENTARIO INTELIGENTE & SPINDLE-OS
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando Contenedores Kafka/Redpanda...
docker compose up -d redpanda redpanda-console 2>nul

echo [2/3] Abriendo Dashboard en el Navegador...
start http://localhost:8000/dashboard

echo [3/3] Levantando Servidor FastAPI & Consumidores de Kafka...
echo.
echo Presiona Ctrl + C en esta ventana cuando desees apagar el servidor.
echo ----------------------------------------------------------------------
echo.

"%~dp0backend\.venv\Scripts\python.exe" -m uvicorn main:app --app-dir "%~dp0backend" --host 0.0.0.0 --port 8000 --reload

pause
