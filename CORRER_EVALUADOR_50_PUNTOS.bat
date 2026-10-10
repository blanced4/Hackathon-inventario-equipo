@echo off
title [EVALUADOR OFICIAL] HackaTecNM - 50 Puntos
color 0A
echo ======================================================================
echo    EJECUTANDO SUITE OFICIAL DE EVALUACION EN DOCKER (50 PUNTOS)
echo ======================================================================
echo.
cd /d "C:\NOVA\hackathon-inventario-kit"
docker compose run --rm contract-tests --api http://host.docker.internal:8000
echo.
echo ======================================================================
echo    PRUEBA FINALIZADA
echo ======================================================================
pause
